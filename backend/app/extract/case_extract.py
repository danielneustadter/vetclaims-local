"""Structured extraction of the case database: every clinical fact with
document+page provenance, plus existing VA ratings from rating decisions.
Map-reduce: pages are batched into windows small enough for reliable local
extraction; each window's events carry the page number they came from."""

from __future__ import annotations

from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from .. import models
from ..db import session
from ..llm import client
from ..llm.queue import job_handler, set_progress

WINDOW_PAGES = 4

_SYSTEM_EVENTS = """You extract clinical facts from a US veteran's records for
a VA disability claim case file. Each page of text is prefixed with its page
number like [page 3]. For every documented diagnosis, complaint, injury,
treatment, exposure, or referral, output one event with:
- page_no: the page number it appears on (from the [page N] marker)
- date: YYYY-MM-DD or YYYY-MM if stated, else empty
- kind: diagnosis | complaint | injury | treatment | exposure | referral
- condition: short standard name of the condition/topic (e.g. "Tinnitus",
  "Right knee strain", "Burn pit exposure")
- detail: one sentence quoting or closely paraphrasing the record
- provider: clinic/provider if stated, else empty
Only output facts that are actually in the text. No duplicates."""


class EventOut(BaseModel):
    page_no: int = 0
    date: str = ""
    kind: str = "complaint"
    condition: str = ""
    detail: str = ""
    provider: str = ""


class EventsOut(BaseModel):
    events: list[EventOut] = Field(default_factory=list)


_SYSTEM_RATINGS = """You extract existing VA disability ratings from a VA
rating decision document. For each service-connected condition list its name,
rating percent (integer), 4-digit diagnostic code if shown, and effective date
(YYYY-MM-DD) if shown. Only what the document actually states."""


class RatingOut(BaseModel):
    condition: str = ""
    percent: int = 0
    diagnostic_code: str = ""
    effective_date: str = ""


class RatingsOut(BaseModel):
    ratings: list[RatingOut] = Field(default_factory=list)


_SYSTEM_MERGE = """You normalize condition names extracted from a veteran's
medical records. Group names that refer to the same underlying medical
condition, and fold treatments/referrals/counseling into the condition they
obviously relate to (e.g. "Audiology referral" and "Hearing conservation
counseling" belong to "Tinnitus"; "Lumbar strain" and "Low back pain" are one
condition). Administrative entries like service entry/separation stay their
own group. canonical must be a proper medical condition name; every input name
must appear in exactly one group's members."""


class MergeGroup(BaseModel):
    canonical: str = ""
    members: list[str] = Field(default_factory=list)


class MergeOut(BaseModel):
    groups: list[MergeGroup] = Field(default_factory=list)


def _merge_conditions(db, case_id: int, job_id: int) -> int:
    names = sorted({e.condition for e in db.scalars(
        select(models.MedicalEvent).where(models.MedicalEvent.case_id == case_id))})
    if len(names) < 2:
        return 0
    set_progress(job_id, "merging condition names")
    out = client.structured(
        MergeOut, _SYSTEM_MERGE,
        "Condition names:\n" + "\n".join(f"- {n}" for n in names)
        + "\n\nGroup them.")
    mapping: dict[str, str] = {}
    for g in out.groups:
        if not g.canonical.strip():
            continue
        for m in g.members:
            mapping[m.strip().lower()] = g.canonical.strip()[:300]
    merged = 0
    for ev in db.scalars(select(models.MedicalEvent)
                         .where(models.MedicalEvent.case_id == case_id)):
        canon = mapping.get(ev.condition.lower())
        if canon and canon != ev.condition:
            ev.condition = canon
            merged += 1
    db.commit()
    return merged


_KINDS = {"diagnosis", "complaint", "injury", "treatment", "exposure", "referral"}


def _windows(pages: list[models.Page]):
    for i in range(0, len(pages), WINDOW_PAGES):
        window = pages[i:i + WINDOW_PAGES]
        text = "\n\n".join(f"[page {p.page_no}]\n{p.text}" for p in window
                           if p.text.strip())
        if text:
            yield window[0].page_no, window[-1].page_no, text


@job_handler("case_extract")
def case_extract(job: models.Job) -> dict:
    case_id = job.payload["case_id"]
    db = session()
    try:
        docs = db.scalars(select(models.Document)
                          .where(models.Document.case_id == case_id,
                                 models.Document.status == "ready")).all()
        # idempotent re-run: rebuild the case DB from scratch
        db.execute(delete(models.MedicalEvent)
                   .where(models.MedicalEvent.case_id == case_id))
        db.execute(delete(models.ExistingRating)
                   .where(models.ExistingRating.case_id == case_id))
        db.commit()

        n_events = n_ratings = 0
        for d_i, doc in enumerate(docs, start=1):
            pages = db.scalars(select(models.Page)
                               .where(models.Page.document_id == doc.id)
                               .order_by(models.Page.page_no)).all()
            for p0, p1, text in _windows(pages):
                set_progress(job.id,
                             f"{doc.filename} p.{p0}-{p1} (doc {d_i}/{len(docs)})")
                out = client.structured(
                    EventsOut, _SYSTEM_EVENTS,
                    f"Records:\n\n{text}\n\nExtract the events.")
                for ev in out.events:
                    if not ev.condition.strip():
                        continue
                    page_no = ev.page_no if p0 <= ev.page_no <= p1 else p0
                    db.add(models.MedicalEvent(
                        case_id=case_id, document_id=doc.id, page_no=page_no,
                        date=ev.date or None,
                        kind=ev.kind if ev.kind in _KINDS else "complaint",
                        condition=ev.condition.strip()[:300],
                        detail=ev.detail.strip(),
                        provider=ev.provider.strip()[:200]))
                    n_events += 1
                db.commit()

            if doc.doc_type == "rating_decision":
                set_progress(job.id, f"ratings from {doc.filename}")
                full = "\n\n".join(p.text for p in pages if p.text.strip())
                rout = client.structured(
                    RatingsOut, _SYSTEM_RATINGS,
                    f"Rating decision:\n\n{full[:20000]}\n\nExtract the ratings.")
                for r in rout.ratings:
                    if not r.condition.strip() or not (0 <= r.percent <= 100):
                        continue
                    db.add(models.ExistingRating(
                        case_id=case_id, document_id=doc.id,
                        condition=r.condition.strip()[:300],
                        percent=r.percent,
                        diagnostic_code=r.diagnostic_code.strip()[:10],
                        effective_date=r.effective_date or None))
                    n_ratings += 1
                db.commit()

        merged = _merge_conditions(db, case_id, job.id)
        return {"documents": len(docs), "events": n_events,
                "ratings": n_ratings, "conditions_merged": merged}
    finally:
        db.close()


def timeline(db, case_id: int) -> list[dict]:
    """Events grouped by condition, each with citations, ordered by first date."""
    events = db.scalars(select(models.MedicalEvent)
                        .where(models.MedicalEvent.case_id == case_id)
                        .order_by(models.MedicalEvent.date)).all()
    groups: dict[str, dict] = {}
    for ev in events:
        key = ev.condition.lower()
        g = groups.setdefault(key, {"condition": ev.condition, "events": []})
        doc = db.get(models.Document, ev.document_id)
        g["events"].append({
            "id": ev.id, "date": ev.date, "kind": ev.kind, "detail": ev.detail,
            "provider": ev.provider, "page_no": ev.page_no,
            "document_id": ev.document_id,
            "filename": doc.filename if doc else "?"})
    return sorted(groups.values(),
                  key=lambda g: min((e["date"] or "9999") for e in g["events"]))
