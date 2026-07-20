"""Deterministic analysis over the case database: claim suggestions with
citations, presumptive eligibility, what-if rating projections, and
evidence-gap checklists. No LLM calls — instant, repeatable, auditable."""

from __future__ import annotations

from sqlalchemy import select

from .. import models, refdata, schemas
from .rating_math import Rating, combined_rating_bilateral, what_if

_EVIDENCE_KINDS = {"diagnosis", "injury", "complaint"}
_ADMIN_WORDS = ("service entry", "separation", "service in ", "entry/separation")

_BILATERAL_HINTS = {
    "legs": ("knee", "ankle", "foot", "hip", "leg", "thigh", "radiculopathy, lower"),
    "arms": ("shoulder", "elbow", "wrist", "hand", "arm", "radiculopathy, upper"),
}


def _bilateral_group(name: str) -> str | None:
    low = name.lower()
    for group, hints in _BILATERAL_HINTS.items():
        if any(h in low for h in hints):
            return group
    return None


def _citations(events: list[models.MedicalEvent], db) -> list[dict]:
    out = []
    for ev in events[:5]:
        doc = db.get(models.Document, ev.document_id)
        out.append({"filename": doc.filename if doc else "?",
                    "page_no": ev.page_no, "date": ev.date,
                    "kind": ev.kind, "detail": ev.detail[:200]})
    return out


def _rating_projection(name: str, current: list[Rating]) -> dict | None:
    matched = refdata.match_diagnostic_code(name)
    if not matched:
        return None
    dc, entry = matched
    tiers = [t["percent"] for t in entry["tiers"] if t["percent"] > 0]
    if not tiers:
        return {"diagnostic_code": dc, "schedule_name": entry["name"],
                "tiers": [], "projections": []}
    group = _bilateral_group(name)
    projections = []
    for pct in (min(tiers), max(tiers)) if len(tiers) > 1 else (tiers[0],):
        w = what_if(current, Rating(pct, group, name))
        projections.append({"at_percent": pct, **w})
    return {"diagnostic_code": dc, "schedule_name": entry["name"],
            "tiers": sorted(set(tiers), reverse=True), "projections": projections}


def _gaps(name: str, events: list[models.MedicalEvent]) -> list[str]:
    gaps = []
    kinds = {e.kind for e in events}
    if not events:
        gaps.append("No documented evidence found in your uploaded records — "
                    "upload treatment records or provide lay statements.")
    if events and "diagnosis" not in kinds:
        gaps.append("No formal diagnosis found in the records — a current "
                    "diagnosis (VA, private, or during a C&P exam) is required "
                    "for service connection.")
    recent = [e for e in events if (e.date or "") >= "2024"]
    if events and not recent:
        gaps.append("No recent treatment documented — evidence that the "
                    "condition is current strengthens the claim.")
    dbq = refdata.find_dbq(name)
    if dbq:
        gaps.append(f"C&P exam will use the {dbq['dbq']}: {dbq['exam']}.")
    return gaps


def analyze(db, case_id: int) -> dict:
    events = db.scalars(select(models.MedicalEvent)
                        .where(models.MedicalEvent.case_id == case_id)).all()
    ratings = db.scalars(select(models.ExistingRating)
                         .where(models.ExistingRating.case_id == case_id)).all()
    conditions = db.scalars(select(models.Condition)
                            .where(models.Condition.case_id == case_id)).all()
    profile_row = db.scalars(select(models.ClaimantProfile)
                             .where(models.ClaimantProfile.case_id == case_id)).first()
    profile = schemas.ClaimantProfileData.model_validate(
        profile_row.data if profile_row else {})

    by_condition: dict[str, list[models.MedicalEvent]] = {}
    for ev in events:
        by_condition.setdefault(ev.condition.lower(), []).append(ev)

    rated_names = [r.condition for r in ratings]
    tracked = {c.name.lower() for c in conditions} | {n.lower() for n in rated_names}
    current = [Rating(r.percent, _bilateral_group(r.condition), r.condition)
               for r in ratings]

    # 1) direct suggestions: documented conditions not yet tracked or rated
    direct = []
    for key, evs in by_condition.items():
        name = evs[0].condition
        low = name.lower()
        if low in tracked or any(w in low for w in _ADMIN_WORDS):
            continue
        if not any(e.kind in _EVIDENCE_KINDS for e in evs):
            continue
        direct.append({
            "name": name, "basis": "direct",
            "why": f"Documented {len(evs)} time(s) in your records with no "
                   "existing rating or tracked claim.",
            "citations": _citations(evs, db),
            "rating": _rating_projection(name, current),
            "gaps": _gaps(name, evs)})

    # 2) secondary suggestions from the curated graph
    anchors = rated_names + [c.name for c in conditions
                             if c.status in ("selected", "claimed", "granted")]
    secondary = []
    seen_targets = set()
    for edge in refdata.secondary_graph():
        anchor = next((a for a in anchors
                       if any(k in a.lower() for k in edge["source"])), None)
        if not anchor:
            continue
        target_low = edge["target"].lower()
        if target_low in seen_targets or target_low in tracked:
            continue
        if any(t in target_low for t in tracked):
            continue
        target_events = [evs for key, evs in by_condition.items()
                         if any(tok in key for tok in target_low.split()[:1])]
        seen_targets.add(target_low)
        secondary.append({
            "name": edge["target"], "basis": "secondary",
            "secondary_to": anchor,
            "why": edge["rationale"],
            "citations": _citations(target_events[0], db) if target_events else [],
            "rating": _rating_projection(edge["target"], current),
            "gaps": [] if target_events else
                    ["Not documented in your records — only pursue this if you "
                     "actually experience it; you would need a current diagnosis "
                     "and a physician's nexus opinion."]})

    # 3) presumptive eligibility
    exposure_text = " ".join(
        [e.detail.lower() + " " + e.condition.lower()
         for e in events if e.kind == "exposure"]
        + [x.lower() for x in profile.service.exposures])
    presumptive = []
    for cat in refdata.presumptives():
        if not any(k in exposure_text for k in cat["exposure_keywords"]):
            continue
        matched_conditions = []
        for cond in cat["conditions"]:
            hit = next((evs for key, evs in by_condition.items()
                        if any(k in key for k in cond["keywords"])), None)
            if hit:
                matched_conditions.append({
                    "name": cond["name"],
                    "citations": _citations(hit, db)})
        presumptive.append({
            "category": cat["label"], "eligibility": cat["eligibility"],
            "documented_matches": matched_conditions})

    return {
        "current_combined": combined_rating_bilateral(current),
        "existing_ratings": [{"condition": r.condition, "percent": r.percent,
                              "diagnostic_code": r.diagnostic_code}
                             for r in ratings],
        "direct_suggestions": direct,
        "secondary_suggestions": secondary,
        "presumptive_eligibility": presumptive,
    }
