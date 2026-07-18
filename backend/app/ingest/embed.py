"""Chunking + embedding into sqlite-vec, with page-span provenance."""

from __future__ import annotations

import struct

from sqlalchemy import select

from .. import models
from ..llm import client

CHUNK_CHARS = 1600


def _pack(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def chunk_pages(pages: list[models.Page]) -> list[tuple[int, int, str]]:
    """Group consecutive pages into ~CHUNK_CHARS chunks; long pages split."""
    chunks: list[tuple[int, int, str]] = []
    buf, start = "", None
    for p in pages:
        text = (p.text or "").strip()
        if not text:
            continue
        if start is None:
            start = p.page_no
        candidate = f"{buf}\n\n{text}".strip()
        if len(candidate) > CHUNK_CHARS and buf:
            chunks.append((start, prev, buf))
            buf, start = text, p.page_no
        else:
            buf = candidate
        prev = p.page_no
        while len(buf) > CHUNK_CHARS * 2:  # very long single page
            chunks.append((start, p.page_no, buf[: CHUNK_CHARS * 2]))
            buf = buf[CHUNK_CHARS * 2:]
            start = p.page_no
    if buf and start is not None:
        chunks.append((start, prev, buf))
    return chunks


def embed_document(db, doc: models.Document) -> int:
    pages = db.scalars(select(models.Page).where(models.Page.document_id == doc.id)
                       .order_by(models.Page.page_no)).all()
    pieces = chunk_pages(pages)
    if not pieces:
        return 0
    vectors = client.embed([t for _, _, t in pieces])
    conn = db.connection().connection
    for (p0, p1, text), vec in zip(pieces, vectors):
        row = models.Chunk(case_id=doc.case_id, document_id=doc.id,
                           page_start=p0, page_end=p1, text=text)
        db.add(row)
        db.flush()
        conn.execute("INSERT INTO vec_chunk(chunk_id, embedding) VALUES (?, ?)",
                     (row.id, _pack(vec)))
    db.commit()
    return len(pieces)


def search(db, case_id: int, query: str, k: int = 8) -> list[dict]:
    [qvec] = client.embed([query])
    conn = db.connection().connection
    rows = conn.execute(
        """SELECT c.id, c.document_id, c.page_start, c.page_end, c.text, v.distance
           FROM vec_chunk v JOIN chunk c ON c.id = v.chunk_id
           WHERE v.embedding MATCH ? AND v.k = ? AND c.case_id = ?
           ORDER BY v.distance""",
        (_pack(qvec), k * 3, case_id)).fetchall()
    out = []
    for cid, doc_id, p0, p1, text, dist in rows[:k]:
        doc = db.get(models.Document, doc_id)
        out.append({"chunk_id": cid, "document_id": doc_id,
                    "filename": doc.filename if doc else "?",
                    "page_start": p0, "page_end": p1,
                    "text": text, "distance": dist})
    return out
