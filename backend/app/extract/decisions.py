"""Decision-letter parsing and AMA appeal-lane recommendation."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from .. import models
from ..db import session
from ..llm import client
from ..llm.queue import job_handler, set_progress

_SYSTEM = """You parse a US VA claim decision letter (or rating decision).
For each issue the letter decides, extract:
- condition: the claimed condition's name
- outcome: granted | denied | deferred
- percent: the evaluation percent if granted (integer), else 0
- effective_date: YYYY-MM-DD if stated, else empty
- reason: the letter's stated reason for the outcome, quoted or closely
  paraphrased (especially the missing element for denials: no diagnosis,
  no nexus, no in-service event, not chronic, etc.)
Also extract decision_date (the letter's date, YYYY-MM-DD) if present.
Only what the letter actually says."""


class IssueOut(BaseModel):
    condition: str = ""
    outcome: str = "denied"
    percent: int = 0
    effective_date: str = ""
    reason: str = ""


class DecisionOut(BaseModel):
    decision_date: str = ""
    issues: list[IssueOut] = Field(default_factory=list)


@job_handler("parse_decision")
def parse_decision(job: models.Job) -> dict:
    doc_id = job.payload["document_id"]
    db = session()
    try:
        doc = db.get(models.Document, doc_id)
        if doc is None:
            raise ValueError("document not found")
        pages = db.scalars(select(models.Page)
                           .where(models.Page.document_id == doc_id)
                           .order_by(models.Page.page_no)).all()
        text = "\n\n".join(p.text for p in pages if p.text.strip())[:30000]
        if not text:
            raise ValueError("document has no extracted text")

        set_progress(job.id, f"parsing {doc.filename}")
        out = client.structured(DecisionOut, _SYSTEM,
                                f"Decision letter:\n\n{text}\n\nParse it.")

        db.execute(delete(models.DecisionIssue)
                   .where(models.DecisionIssue.document_id == doc_id))
        n = 0
        for issue in out.issues:
            if not issue.condition.strip():
                continue
            db.add(models.DecisionIssue(
                case_id=doc.case_id, document_id=doc_id,
                decision_date=out.decision_date or None,
                condition=issue.condition.strip()[:300],
                outcome=issue.outcome if issue.outcome in
                        ("granted", "denied", "deferred") else "denied",
                percent=issue.percent if 0 < issue.percent <= 100 else None,
                effective_date=issue.effective_date or None,
                reason=issue.reason.strip()))
            n += 1
        db.commit()
        return {"issues": n, "decision_date": out.decision_date}
    finally:
        db.close()


def recommend(issues: list[models.DecisionIssue]) -> list[dict]:
    """Deterministic AMA-lane guidance per denied/deferred issue."""
    out = []
    for issue in issues:
        if issue.outcome == "granted":
            continue
        reason = issue.reason.lower()
        deadline = ""
        if issue.decision_date:
            try:
                d = dt.date.fromisoformat(issue.decision_date[:10])
                deadline = (d + dt.timedelta(days=365)).isoformat()
            except ValueError:
                pass
        if any(k in reason for k in ("no current diagnosis", "no diagnosis",
                                     "no evidence of a current", "no nexus",
                                     "not related", "no medical opinion",
                                     "insufficient evidence", "no record of")):
            lane, form = "supplemental", "20-0995"
            why = ("The denial hinges on missing evidence. A Supplemental Claim "
                   "lets you add new and relevant evidence (new diagnosis, nexus "
                   "letter, lay statements) — the strongest fix for this denial.")
        elif any(k in reason for k in ("error", "overlooked", "failed to consider",
                                       "did not consider", "incorrectly")):
            lane, form = "hlr", "20-0996"
            why = ("The record already supports the claim and the VA appears to "
                   "have made an error. Higher-Level Review puts a senior "
                   "reviewer on the same record — no new evidence allowed.")
        else:
            lane, form = "supplemental", "20-0995"
            why = ("Default recommendation: a Supplemental Claim keeps the door "
                   "open for new evidence. Consider a Board appeal (VA Form "
                   "10182) instead if you believe a judge must weigh the "
                   "existing evidence differently.")
        out.append({"issue_id": issue.id, "condition": issue.condition,
                    "outcome": issue.outcome, "reason": issue.reason,
                    "lane": lane, "form": form, "why": why,
                    "deadline": deadline,
                    "deadline_note": "All AMA lanes: 1 year from the decision "
                                     "date to keep your effective date."})
    return out
