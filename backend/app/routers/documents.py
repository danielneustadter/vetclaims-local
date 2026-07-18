import re
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from ..db import get_db
from ..ingest.textract import sha256_file
from ..llm.queue import enqueue

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/cases/{case_id}/documents")
def upload_document(case_id: int, file: UploadFile, db: Session = Depends(get_db)):
    if not db.get(models.Case, case_id):
        raise HTTPException(404, "case not found")
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(400, "only PDF uploads are supported")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
    case_dir = settings.uploads_dir / str(case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    dest = case_dir / safe
    n = 1
    while dest.exists():
        dest = case_dir / f"{dest.stem.rstrip('_0123456789')}_{n}{dest.suffix}"
        n += 1
    with dest.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    doc = models.Document(case_id=case_id, filename=file.filename,
                          stored_path=str(dest), sha256=sha256_file(dest))
    db.add(doc)
    db.commit()
    job_id = enqueue("extract_text", {"document_id": doc.id})
    return {"id": doc.id, "filename": doc.filename, "job_id": job_id}


@router.get("/documents/{doc_id}/pages")
def document_pages(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if not doc:
        raise HTTPException(404)
    pages = db.scalars(select(models.Page).where(models.Page.document_id == doc_id)
                       .order_by(models.Page.page_no)).all()
    return {"id": doc.id, "filename": doc.filename, "status": doc.status,
            "pages": [{"page_no": p.page_no, "text_source": p.text_source,
                       "chars": len(p.text),
                       "preview": p.text[:400]} for p in pages]}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if not doc:
        raise HTTPException(404)
    db.delete(doc)
    db.commit()
    return {"ok": True}
