"""Ingestion unit tests (no LLM required)."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.ingest.embed import chunk_pages, CHUNK_CHARS


def _page(no: int, text: str):
    return SimpleNamespace(page_no=no, text=text)


def test_chunk_pages_groups_and_provenance():
    pages = [_page(1, "a" * 700), _page(2, "b" * 700), _page(3, "c" * 700),
             _page(4, ""), _page(5, "d" * 100)]
    chunks = chunk_pages(pages)  # type: ignore[arg-type]
    assert chunks, "produced no chunks"
    # every chunk respects the size cap (with the 2x page-split allowance)
    assert all(len(t) <= CHUNK_CHARS * 2 for _, _, t in chunks)
    # provenance covers all non-empty pages in order
    assert chunks[0][0] == 1
    assert chunks[-1][1] == 5
    joined = "".join(t for _, _, t in chunks)
    for ch in "abcd":
        assert ch in joined


def test_chunk_pages_empty():
    assert chunk_pages([_page(1, ""), _page(2, "  ")]) == []  # type: ignore[arg-type]


@pytest.mark.skipif(importlib.util.find_spec("rapidocr_onnxruntime") is None,
                    reason="rapidocr not installed")
def test_ocr_scanned_fixture(tmp_path: Path):
    from tests.fixtures.make_fixtures import make_scanned_str
    from app.ingest.ocr import ocr_pdf_page

    pdf = tmp_path / "scanned.pdf"
    make_scanned_str(pdf)

    # confirm the fixture truly has no text layer
    import fitz
    doc = fitz.open(str(pdf))
    assert len(doc[0].get_text().strip()) < 30
    doc.close()

    text = ocr_pdf_page(str(pdf), 1).lower()
    assert "back pain" in text or "lumbar" in text
