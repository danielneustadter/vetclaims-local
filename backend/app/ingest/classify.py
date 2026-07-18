"""Document-type classification with the fast model (falls back to primary
when the fast model isn't pulled)."""

from __future__ import annotations

from pydantic import BaseModel

from ..config import settings
from ..llm import client

DOC_TYPES = ["str", "dd214", "rating_decision", "decision_letter",
             "private_treatment", "dbq", "va_treatment", "other"]

_SYSTEM = """Classify a US veteran's document from its first page(s).
Types:
- str: military service treatment record / sick-call / clinic note during service
- dd214: DD-214 discharge certificate / separation document
- rating_decision: VA rating decision listing service-connected percentages
- decision_letter: VA claim decision notification letter
- private_treatment: civilian/private medical record
- va_treatment: VA medical center treatment record (post-service)
- dbq: Disability Benefits Questionnaire
- other: anything else"""


class DocClass(BaseModel):
    doc_type: str = "other"


def _fast_model() -> str:
    missing = client.status().get("missing_models", [])
    return settings.model_primary if settings.model_fast in missing else settings.model_fast


def classify(first_pages_text: str) -> str:
    out = client.structured(
        DocClass, _SYSTEM,
        f"Document begins:\n\n{first_pages_text[:4000]}\n\nClassify it.",
        model=_fast_model())
    return out.doc_type if out.doc_type in DOC_TYPES else "other"
