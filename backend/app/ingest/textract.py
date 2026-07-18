"""Native PDF text extraction (PyMuPDF). Pages whose text layer is empty or
near-empty are marked text_source="none" and picked up by the OCR pass
(Epic 2)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import fitz  # PyMuPDF

from .. import models
from ..db import session
from ..llm.queue import job_handler, set_progress

MIN_CHARS_FOR_NATIVE = 30


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@job_handler("extract_text")
def extract_text(job: models.Job) -> dict:
    doc_id = job.payload["document_id"]
    db = session()
    try:
        document = db.get(models.Document, doc_id)
        if document is None:
            raise ValueError(f"document {doc_id} not found")
        document.status = "extracting"
        db.commit()

        pdf = fitz.open(document.stored_path)
        try:
            document.page_count = pdf.page_count
            native_pages = 0
            for i, page in enumerate(pdf, start=1):
                if i % 10 == 0:
                    set_progress(job.id, f"page {i}/{pdf.page_count}")
                text = page.get_text("text").strip()
                source = "native" if len(text) >= MIN_CHARS_FOR_NATIVE else "none"
                native_pages += source == "native"
                db.add(models.Page(document_id=doc_id, page_no=i,
                                   text=text, text_source=source))
            db.commit()
        finally:
            pdf.close()

        # OCR the pages that had no usable text layer
        from sqlalchemy import select
        from . import ocr
        ocr_pages = db.scalars(
            select(models.Page).where(models.Page.document_id == doc_id,
                                      models.Page.text_source == "none")).all()
        ocred = 0
        for n, p in enumerate(ocr_pages, start=1):
            set_progress(job.id, f"OCR page {p.page_no} ({n}/{len(ocr_pages)})")
            text = ocr.ocr_pdf_page(document.stored_path, p.page_no)
            if len(text.strip()) >= MIN_CHARS_FOR_NATIVE:
                p.text, p.text_source = text, "ocr"
                ocred += 1
        db.commit()

        # classify + embed
        from . import classify as _classify, embed as _embed
        set_progress(job.id, "classifying document")
        first_pages = db.scalars(
            select(models.Page).where(models.Page.document_id == doc_id)
            .order_by(models.Page.page_no).limit(2)).all()
        try:
            document.doc_type = _classify.classify(
                "\n\n".join(p.text for p in first_pages))
        except Exception:
            document.doc_type = "unknown"
        set_progress(job.id, "embedding text")
        try:
            n_chunks = _embed.embed_document(db, document)
        except Exception:
            n_chunks = -1  # embedding is best-effort; search degrades gracefully
        document.status = "ready"
        db.commit()
        return {"pages": document.page_count, "native_pages": native_pages,
                "ocr_pages": ocred, "doc_type": document.doc_type,
                "chunks": n_chunks}
    except Exception:
        db.rollback()
        doc = db.get(models.Document, doc_id)
        if doc:
            doc.status = "error"
            db.commit()
        raise
    finally:
        db.close()
