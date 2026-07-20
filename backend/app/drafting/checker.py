"""Grounding checker: verifies a drafted statement against the documented
facts it was generated from. Uses a structured LLM verification pass — the
draft is the claim set, the fact block is the only allowed source — and flags
any factual assertion without support. Flagged sentences are shown to the
veteran in the draft editor; they decide whether to fix or delete them."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..llm import client

_SYSTEM = """You are verifying a draft VA claim statement against the source
facts it must be based on. List every sentence (verbatim) from the draft that
asserts a specific factual event, date, symptom, provider, or exposure that is
NOT supported by the source facts. General first-person experience phrasing
("it bothers me daily") is acceptable if consistent with the facts; concrete
inventions (new incidents, new dates, new treatments) are not. If everything
is supported, return an empty list."""


class GroundingReport(BaseModel):
    unsupported: list[str] = Field(default_factory=list)


def ground_check(draft_text: str, facts: str) -> dict:
    try:
        report = client.structured(
            GroundingReport, _SYSTEM,
            f"SOURCE FACTS:\n{facts}\n\nDRAFT:\n{draft_text}\n\n"
            "List unsupported factual sentences.")
        # keep only sentences that actually occur in the draft (guards against
        # the checker itself hallucinating)
        confirmed = [s for s in report.unsupported
                     if s.strip() and s.strip()[:60].lower() in draft_text.lower()]
        return {"unsupported": confirmed, "checked": True}
    except Exception as exc:  # checker failure must not block drafting
        return {"unsupported": [], "checked": False, "error": str(exc)[:200]}
