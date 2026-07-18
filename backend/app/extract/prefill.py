"""LLM pre-fill of the claimant profile from uploaded records. Map-reduce:
each document contributes a partial ProfilePrefill from its first pages, then
partials merge (first non-empty wins; conditions concatenate). Everything the
model produces is a draft the veteran edits in the Profile screen."""

from __future__ import annotations

from sqlalchemy import select

from .. import models, schemas
from ..db import session
from ..llm import client
from ..llm.queue import job_handler, set_progress

_SYSTEM_IDENTITY = """You extract veteran identity and service facts from US
military and medical records to pre-fill a VA disability claim form. Return
only facts explicitly present in the text; use empty strings otherwise.
Names often appear as "LAST, FIRST MIDDLE" — split them into the separate
fields. Example: "SMITH, JOHN A" means first_name="John",
middle_initial="A", last_name="Smith" — never leave first_name empty when a
full name is present. SSNs may be formatted ###-##-####. Dates must be YYYY-MM-DD (or
YYYY-MM if the day is unknown). Entry/separation dates and branch belong in
service.periods. Exposures (burn pits, asbestos, radiation, Agent Orange,
Camp Lejeune water, etc.) go in service.exposures."""

_SYSTEM_CONDITIONS = """You review US military medical records for a VA
disability claim. List diagnosed conditions, injuries, or chronic documented
complaints that could relate to military service. For each give the standard
condition name, onset_date (YYYY-MM if known), and a short evidence_note
quoting or closely paraphrasing where it appears in the records. Do not invent
conditions that are not documented."""

_PER_DOC_CHAR_BUDGET = 24_000


def _doc_excerpt(db, doc: models.Document) -> str:
    pages = db.scalars(
        select(models.Page).where(models.Page.document_id == doc.id)
        .order_by(models.Page.page_no)).all()
    parts, used = [], 0
    for p in pages:
        if not p.text:
            continue
        take = p.text[: _PER_DOC_CHAR_BUDGET - used]
        parts.append(f"[{doc.filename} p.{p.page_no}]\n{take}")
        used += len(take)
        if used >= _PER_DOC_CHAR_BUDGET:
            break
    return "\n\n".join(parts)


def _period_score(p) -> int:
    """Completeness score: a DD-214-style period (entry+separation+branch)
    beats a stray date pulled from a clinic note."""
    return (2 * bool(p.entry_date) + 2 * bool(p.separation_date)
            + bool(p.branch) + bool(p.character_of_discharge))


def _real_periods(periods):
    """Drop placeholder rows the model returns with no actual content."""
    return [p for p in periods if _period_score(p) > 0]


def _best_periods(a, b):
    a, b = _real_periods(a), _real_periods(b)
    if not a or not b:
        return a or b
    return a if max(map(_period_score, a)) >= max(map(_period_score, b)) else b


def _merge(base: schemas.ProfilePrefill, extra: schemas.ProfilePrefill) -> None:
    for section in ("identity",):
        b, e = getattr(base, section), getattr(extra, section)
        for field in type(b).model_fields:
            if not getattr(b, field) and getattr(e, field):
                setattr(b, field, getattr(e, field))
    base.service.periods = _best_periods(base.service.periods,
                                         extra.service.periods)
    base.service.exposures = list(dict.fromkeys(
        base.service.exposures + extra.service.exposures))
    base.service.combat_service = base.service.combat_service or extra.service.combat_service
    seen = {c.name.lower() for c in base.candidate_conditions}
    for c in extra.candidate_conditions:
        if c.name.lower() not in seen:
            base.candidate_conditions.append(c)
            seen.add(c.name.lower())


def _normalize_identity(ident: schemas.VeteranIdentity) -> None:
    """Deterministic cleanup for 'LAST, FIRST M' the model didn't split."""
    if "," in ident.last_name and not ident.first_name:
        last, _, rest = ident.last_name.partition(",")
        parts = rest.strip().split()
        ident.last_name = last.strip().title()
        if parts:
            ident.first_name = parts[0].title()
        if len(parts) > 1 and not ident.middle_initial:
            ident.middle_initial = parts[1][0].upper()
    for field in ("first_name", "last_name"):
        v = getattr(ident, field)
        if v.isupper() and len(v) > 2:
            setattr(ident, field, v.title())


@job_handler("profile_prefill")
def profile_prefill(job: models.Job) -> dict:
    case_id = job.payload["case_id"]
    db = session()
    try:
        docs = db.scalars(
            select(models.Document)
            .where(models.Document.case_id == case_id,
                   models.Document.status == "ready")).all()
        if not docs:
            raise ValueError("no processed documents to pre-fill from")

        merged = schemas.ProfilePrefill()
        for n, doc in enumerate(docs, start=1):
            set_progress(job.id, f"analyzing {doc.filename} ({n}/{len(docs)})")
            excerpt = _doc_excerpt(db, doc)
            if not excerpt:
                continue
            ident = client.structured(
                schemas.IdentityPrefill, _SYSTEM_IDENTITY,
                f"Records excerpt:\n\n{excerpt}\n\nExtract identity and service facts.")
            conds = client.structured(
                schemas.ConditionsPrefill, _SYSTEM_CONDITIONS,
                f"Records excerpt:\n\n{excerpt}\n\nList the documented conditions.")
            partial = schemas.ProfilePrefill(
                identity=ident.identity, service=ident.service,
                candidate_conditions=conds.candidate_conditions)
            _normalize_identity(partial.identity)
            _merge(merged, partial)

        profile = db.scalars(select(models.ClaimantProfile)
                             .where(models.ClaimantProfile.case_id == case_id)).first()
        if profile is None:
            profile = models.ClaimantProfile(case_id=case_id, data={})
            db.add(profile)
        data = schemas.ClaimantProfileData.model_validate(profile.data or {})
        # prefill fills gaps only — never overwrites what the veteran typed
        for field in type(data.identity).model_fields:
            if not getattr(data.identity, field) and getattr(merged.identity, field):
                setattr(data.identity, field, getattr(merged.identity, field))
        if not _real_periods(data.service.periods):
            data.service.periods = _real_periods(merged.service.periods)
        data.service.exposures = list(dict.fromkeys(
            data.service.exposures + merged.service.exposures))
        profile.data = data.model_dump()

        existing = {c.name.lower() for c in db.scalars(
            select(models.Condition).where(models.Condition.case_id == case_id))}
        added = 0
        for c in merged.candidate_conditions:
            if c.name.lower() in existing:
                continue
            if c.onset_date and c.onset_date.endswith("-00"):
                c.onset_date = c.onset_date[:-3]  # "2012-06-00" → "2012-06"
            db.add(models.Condition(
                case_id=case_id, name=c.name, basis=c.basis or "direct",
                onset_date=c.onset_date, notes=c.evidence_note,
                status="suggested", sort=100 + added))
            added += 1
        db.commit()
        return {"documents_analyzed": len(docs),
                "conditions_suggested": added}
    finally:
        db.close()
