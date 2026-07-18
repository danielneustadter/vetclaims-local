"""OCR for scanned pages via RapidOCR (pure-pip ONNX models, fully offline).
Loaded lazily — first call takes a few seconds to init the models."""

from __future__ import annotations

import logging

import fitz

log = logging.getLogger("vetclaims.ocr")
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def ocr_pdf_page(pdf_path: str, page_no: int) -> str:
    """Rasterize one 1-based page at 300dpi-ish and OCR it."""
    doc = fitz.open(pdf_path)
    try:
        page = doc[page_no - 1]
        pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), colorspace=fitz.csGRAY)
        img = pix.tobytes("png")
    finally:
        doc.close()
    result, _ = _get_engine()(img)
    if not result:
        return ""
    return "\n".join(line[1] for line in result)
