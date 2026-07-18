"""Extraction-recall test against the fictional fixture case.

Requires a running Ollama with the configured primary model, so it is skipped
unless VETCLAIMS_LLM_TESTS=1. Run:
    VETCLAIMS_LLM_TESTS=1 pytest tests/test_extraction_recall.py -q
"""

import os

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("VETCLAIMS_LLM_TESTS") != "1",
                                reason="LLM tests disabled (set VETCLAIMS_LLM_TESTS=1)")

# planted ground truth in tests/fixtures/make_fixtures.py
PLANTED_CONDITIONS = {
    "tinnitus": ["tinnitus"],
    "knee": ["knee"],
    "rhinitis/respiratory": ["rhinitis", "sinus", "respiratory"],
    "behavioral health": ["ptsd", "adjustment"],
    "low back (OCR page)": ["back", "lumbar"],
}
PLANTED_RATINGS = {("6260", 10), ("5257", 10)}


def test_case_extract_recall(tmp_path):
    from tests.fixtures import make_fixtures as mf
    from app.llm import client as llm

    if llm.status()["ollama"] != "up":
        pytest.skip("Ollama not running")

    files = {
        "str.pdf": mf.make_str, "dd214.pdf": mf.make_dd214,
        "rating.pdf": mf.make_rating_decision, "scan.pdf": mf.make_scanned_str,
    }
    for name, fn in files.items():
        fn(tmp_path / name)

    # run ingestion + extraction against an isolated temp DB via the app layer
    os.environ["VETCLAIMS_DATA_DIR"] = str(tmp_path / "data")
    import importlib
    from app import config
    importlib.reload(config)
    from app import db as app_db
    importlib.reload(app_db)
    # NOTE: full-app reload wiring is heavyweight; this test drives the
    # extraction prompt directly instead, asserting recall of planted facts.
    import fitz
    from app.extract.case_extract import EventsOut, _SYSTEM_EVENTS, RatingsOut, _SYSTEM_RATINGS

    all_text = []
    for name in ("str.pdf", "scan.pdf"):
        doc = fitz.open(str(tmp_path / name))
        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if not text and name == "scan.pdf":
                from app.ingest.ocr import ocr_pdf_page
                text = ocr_pdf_page(str(tmp_path / name), i)
            all_text.append(f"[page {i}]\n{text}")
        doc.close()

    out = llm.structured(EventsOut, _SYSTEM_EVENTS,
                         "Records:\n\n" + "\n\n".join(all_text)
                         + "\n\nExtract the events.")
    found = " ".join(e.condition.lower() for e in out.events)
    missed = [label for label, keys in PLANTED_CONDITIONS.items()
              if not any(k in found for k in keys)]
    assert not missed, f"extraction missed planted conditions: {missed}"

    doc = fitz.open(str(tmp_path / "rating.pdf"))
    rating_text = "\n".join(p.get_text() for p in doc)
    doc.close()
    rout = llm.structured(RatingsOut, _SYSTEM_RATINGS,
                          f"Rating decision:\n\n{rating_text}\n\nExtract the ratings.")
    got = {(r.diagnostic_code, r.percent) for r in rout.ratings}
    assert PLANTED_RATINGS <= got, f"missing ratings: {PLANTED_RATINGS - got}"
