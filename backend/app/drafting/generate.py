"""Draft generation. Personal statements are the only free-text LLM output in
the app, and they run through the grounding checker (checker.py) before the
veteran sees them. Nexus outlines, C&P prep sheets, and lay templates are
deterministic — built from refdata and the case database, no generation."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from .. import models, refdata, schemas
from ..db import session
from ..llm import client
from ..llm.queue import job_handler, set_progress
from .checker import ground_check

_STMT_SYSTEM = """You draft a first-person personal statement (for VA Form
21-4138) for a veteran's disability claim. STRICT RULES:
- Use ONLY the facts provided. Never invent events, dates, symptoms,
  providers, or feelings that are not in the facts.
- Write plainly and specifically, first person, past-to-present structure:
  what happened in service, symptoms then, continuity since, impact today.
- Where a fact comes from a record, keep its date.
- 250-450 words. No headings, no bullet lists — flowing paragraphs.
- Do not exaggerate or minimize. Do not give legal or medical opinions.
- End with: the statement is true to the best of the veteran's knowledge."""


def _condition_facts(db, case_id: int, condition: models.Condition) -> tuple[str, list[dict]]:
    """Collect the fact block + citation list for one condition."""
    key = condition.name.lower().split(",")[0].split("(")[0].strip()
    events = [e for e in db.scalars(
        select(models.MedicalEvent).where(models.MedicalEvent.case_id == case_id)
        .order_by(models.MedicalEvent.date))
        if key in e.condition.lower() or e.condition.lower() in key]
    profile_row = db.scalars(select(models.ClaimantProfile)
                             .where(models.ClaimantProfile.case_id == case_id)).first()
    profile = schemas.ClaimantProfileData.model_validate(
        profile_row.data if profile_row else {})

    lines, cites = [], []
    if profile.service.periods:
        sp = profile.service.periods[0]
        lines.append(f"- Service: {sp.branch or 'military'} "
                     f"{sp.entry_date or '?'} to {sp.separation_date or '?'}")
    lines.append(f"- Claimed condition: {condition.name} "
                 f"(basis: {condition.basis}"
                 + (f", secondary to {condition.secondary_to}" if condition.secondary_to else "")
                 + (f", exposure: {condition.exposure}" if condition.exposure else "") + ")")
    if condition.onset_date:
        lines.append(f"- Approximate onset: {condition.onset_date}")
    if condition.notes:
        lines.append(f"- Veteran's note: {condition.notes}")
    for e in events:
        doc = db.get(models.Document, e.document_id)
        fname = doc.filename if doc else "?"
        lines.append(f"- [{e.date or 'undated'}] ({e.kind}) {e.detail}"
                     + (f" — {e.provider}" if e.provider else "")
                     + f" (source: {fname} p.{e.page_no})")
        cites.append({"filename": fname, "page_no": e.page_no,
                      "date": e.date, "detail": e.detail})
    return "\n".join(lines), cites


@job_handler("draft_statement")
def draft_statement(job: models.Job) -> dict:
    cond_id = job.payload["condition_id"]
    db = session()
    try:
        condition = db.get(models.Condition, cond_id)
        if condition is None:
            raise ValueError("condition not found")
        case_id = condition.case_id
        facts, cites = _condition_facts(db, case_id, condition)

        set_progress(job.id, f"drafting statement for {condition.name}")
        content = client.draft(
            _STMT_SYSTEM,
            f"Documented facts:\n{facts}\n\nDraft the personal statement.")

        set_progress(job.id, "checking draft against your records")
        grounding = ground_check(content, facts)

        draft = models.Draft(
            case_id=case_id, condition_id=cond_id, kind="personal_statement",
            title=f"Personal statement — {condition.name}",
            content=content.strip(),
            grounding={"citations": cites, **grounding})
        db.add(draft)
        db.commit()
        return {"draft_id": draft.id,
                "unsupported_claims": len(grounding.get("unsupported", []))}
    finally:
        db.close()


_REBUTTAL_SYSTEM = """You draft a first-person statement (for VA Form 21-4138
or a Supplemental Claim) responding to a VA denial. STRICT RULES:
- Use ONLY the provided facts and the denial reason. Never invent evidence.
- Address the denial reason head-on: point at the documented facts that answer
  it, by date and source, and state plainly what new evidence the veteran is
  submitting or seeking if the record lacks it.
- Respectful, factual tone. 200-350 words, flowing paragraphs.
- End with: the statement is true to the best of the veteran's knowledge."""


@job_handler("draft_rebuttal")
def draft_rebuttal(job: models.Job) -> dict:
    issue_id = job.payload["issue_id"]
    db = session()
    try:
        issue = db.get(models.DecisionIssue, issue_id)
        if issue is None:
            raise ValueError("decision issue not found")
        case_id = issue.case_id
        condition = models.Condition(name=issue.condition, basis="direct",
                                     notes="", case_id=case_id)
        facts, cites = _condition_facts(db, case_id, condition)

        set_progress(job.id, f"drafting rebuttal for {issue.condition}")
        content = client.draft(
            _REBUTTAL_SYSTEM,
            f"Denied condition: {issue.condition}\n"
            f"VA's stated reason: {issue.reason or 'not stated'}\n"
            f"Decision date: {issue.decision_date or 'unknown'}\n\n"
            f"Documented facts:\n{facts}\n\nDraft the rebuttal statement.")
        set_progress(job.id, "checking draft against your records")
        grounding = ground_check(content, facts + f"\nDenial reason: {issue.reason}")

        draft = models.Draft(
            case_id=case_id, condition_id=None, kind="personal_statement",
            title=f"Rebuttal statement — {issue.condition}",
            content=content.strip(), grounding={"citations": cites, **grounding})
        db.add(draft)
        db.commit()
        return {"draft_id": draft.id,
                "unsupported_claims": len(grounding.get("unsupported", []))}
    finally:
        db.close()


# ---------- deterministic drafts ----------

def nexus_outline(db, condition: models.Condition, case_id: int) -> str:
    edge = next((e for e in refdata.secondary_graph()
                 if condition.secondary_to
                 and any(k in condition.secondary_to.lower() for k in e["source"])
                 and e["target"].lower().split()[0] in condition.name.lower()),
                None)
    rationale = edge["rationale"] if edge else (
        "The examining physician should address whether the claimed condition "
        "was at least as likely as not caused or aggravated by the veteran's "
        "service or service-connected condition.")
    facts, _ = _condition_facts(db, case_id, condition)
    matched = refdata.match_diagnostic_code(condition.name)
    dc_line = (f"Relevant diagnostic code: {matched[0]} — {matched[1]['name']}"
               if matched else "")
    return f"""# Nexus letter outline — {condition.name}

**Give this outline to your treating physician.** A nexus letter is their
independent medical opinion; this outline only lists what the letter needs to
cover. The physician must review the records and reach their own conclusion.

## What the letter must contain
1. Physician's credentials and treatment relationship with the veteran.
2. Statement that they reviewed the veteran's service treatment records
   (list reviewed documents).
3. Current diagnosis of: {condition.name}. {dc_line}
4. The medical opinion, using VA's standard of proof, e.g.:
   "It is at least as likely as not (50% or greater probability) that the
   veteran's {condition.name} {"was caused or aggravated by their service-connected " + condition.secondary_to if condition.secondary_to else "began during or was caused by their military service"}."
5. The medical rationale, in the physician's own words. Relevant mechanism:
   {rationale}
6. Signature, date, and contact information.

## Documented evidence to hand the physician
{facts}
"""


def cp_prep(condition: models.Condition) -> str:
    dbq = refdata.find_dbq(condition.name)
    matched = refdata.match_diagnostic_code(condition.name)
    tier_lines = ""
    if matched and matched[1]["tiers"]:
        tier_lines = "\n".join(
            f"- **{t['percent']}%** — {t['criteria'][:300]}"
            for t in matched[1]["tiers"])
    return f"""# C&P exam preparation — {condition.name}

A Compensation & Pension exam is a medical evaluation, not an interview to
"pass". Be completely honest and complete. Two rules: never exaggerate, and
never minimize (many veterans understate their worst days).

## What the examiner will use
{f"- DBQ: **{dbq['dbq']}**\\n- Exam focus: {dbq['exam']}" if dbq else "- Ask which DBQ applies to this condition."}
{f'''
## How the VA rates this condition ({matched[0]} — {matched[1]["name"]})
{tier_lines}
''' if tier_lines else ""}
## Before the exam
- Review your own timeline for this condition (Case File tab) so dates are fresh.
- Write down your worst-day symptoms and how often they happen.
- List every way it affects work, chores, sleep, driving, relationships.

## During the exam
- Describe your **typical bad day**, not your best day.
- If pain limits motion, say so when it starts hurting — do not push through.
- Mention flare-ups: frequency, duration, and what they stop you doing.
- If the examiner rushes, state clearly what they did not ask about.

*This sheet is informational only and is not medical or legal advice.*
"""


def lay_template(condition: models.Condition, veteran_name: str) -> str:
    return f"""# Lay (buddy) statement template — {condition.name}

Give this to a spouse, family member, friend, or fellow service member who has
witnessed your condition. They should write in their own words — this is only
a structure. It can be submitted on VA Form 21-10210 (Lay/Witness Statement).

---

**Statement in support of the claim of {veteran_name}**

1. Who I am: name, relationship to the veteran, and how long I have known them.
2. What I observed BEFORE service (if applicable): the veteran's health and
   activities before they served.
3. What I observed DURING/AFTER service about their {condition.name}:
   specific incidents, symptoms I have personally seen, and when they started.
4. How it affects them today: concrete examples (sleep, work, mood, mobility,
   activities they stopped doing).
5. Certification: "I certify that the above statements are true and correct to
   the best of my knowledge and belief." — signature, printed name, date.
"""
