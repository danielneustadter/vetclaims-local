"""Reference data loaders: 38 CFR Part 4 rating schedule (built from the eCFR
by scripts/build_rating_schedule.py), curated secondary-condition graph,
presumptive categories, and DBQ map."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).parent / "data"


@lru_cache(maxsize=1)
def rating_schedule() -> dict[str, dict]:
    return json.loads((DATA / "rating_schedule.json").read_text(encoding="utf-8"))["codes"]


@lru_cache(maxsize=1)
def secondary_graph() -> list[dict]:
    return json.loads((DATA / "secondary_graph.json").read_text(encoding="utf-8"))["edges"]


@lru_cache(maxsize=1)
def presumptives() -> list[dict]:
    return json.loads((DATA / "presumptives.json").read_text(encoding="utf-8"))["categories"]


@lru_cache(maxsize=1)
def dbq_map() -> list[dict]:
    return json.loads((DATA / "dbq_map.json").read_text(encoding="utf-8"))["map"]


_STOP = {"of", "the", "and", "or", "with", "other", "due", "to", "chronic",
         "condition", "disorder", "disease", "syndrome", "strain", "left",
         "right", "bilateral"}


# curated overrides for the most commonly claimed conditions; checked before
# the fuzzy matcher because schedule names are often non-obvious
# ("Allergic or vasomotor rhinitis", "Lumbosacral or cervical strain")
_DC_OVERRIDES: list[tuple[tuple[str, ...], str]] = [
    (("tinnitus",), "6260"),
    (("hearing loss",), "6100"),
    (("ptsd", "post-traumatic stress", "posttraumatic stress"), "9411"),
    (("adjustment disorder",), "9440"),
    (("major depressive", "depression"), "9434"),
    (("generalized anxiety", "anxiety disorder"), "9400"),
    (("rhinitis",), "6522"),
    (("sinusitis",), "6510"),
    (("asthma",), "6602"),
    (("sleep apnea",), "6847"),
    (("low back", "lumbar strain", "lumbosacral", "back strain", "back pain"), "5237"),
    (("cervical strain", "neck strain", "neck pain"), "5237"),
    (("degenerative arthritis", "osteoarthritis"), "5003"),
    (("intervertebral disc", "ivds", "herniated disc"), "5243"),
    (("radiculopathy", "sciatic"), "8520"),
    (("knee",), "5257"),
    (("migraine", "headache"), "8100"),
    (("hypertension", "high blood pressure"), "7101"),
    (("gerd", "reflux"), "7203"),
    (("irritable bowel", "ibs"), "7319"),
    (("diabetes",), "7913"),
    (("peripheral neuropathy",), "8520"),
    (("pes planus", "flat feet", "flatfoot"), "5276"),
    (("plantar fasciitis",), "5269"),
    (("erectile dysfunction",), "7522"),
    (("scar",), "7804"),
    (("tbi", "traumatic brain injury"), "8045"),
]


def match_diagnostic_code(condition_name: str) -> tuple[str, dict] | None:
    """Best-effort match of a condition name to a diagnostic code: curated
    overrides first, then deterministic keyword scoring. No LLM."""
    low = condition_name.lower()
    schedule = rating_schedule()
    for keywords, dc in _DC_OVERRIDES:
        if any(k in low for k in keywords) and dc in schedule:
            return dc, schedule[dc]
    tokens = {t for t in _tokens(condition_name) if t not in _STOP}
    if not tokens:
        return None
    best, best_score = None, 0.0
    for dc, entry in rating_schedule().items():
        name_tokens = {t for t in _tokens(entry["name"]) if t not in _STOP}
        if not name_tokens:
            continue
        overlap = tokens & name_tokens
        if not overlap:
            continue
        score = len(overlap) / len(tokens | name_tokens) + 0.3 * (len(overlap) / len(tokens))
        if entry["tiers"]:
            score += 0.05  # prefer codes we can project ratings for
        if score > best_score:
            best, best_score = (dc, entry), score
    return best if best_score >= 0.25 else None


def find_dbq(condition_name: str) -> dict | None:
    low = condition_name.lower()
    for row in dbq_map():
        if any(k in low for k in row["keywords"]):
            return row
    return None


def _tokens(s: str) -> list[str]:
    out, cur = [], []
    for ch in s.lower():
        if ch.isalnum():
            cur.append(ch)
        elif cur:
            out.append("".join(cur))
            cur = []
    if cur:
        out.append("".join(cur))
    return out
