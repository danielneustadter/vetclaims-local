from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..llm import client as llm_client
from ..llm.queue import enqueue

router = APIRouter(prefix="/api", tags=["cases"])


class CaseIn(BaseModel):
    title: str = "My VA Claim"


@router.get("/health")
def health():
    return {"status": "ok", "llm": llm_client.status()}


@router.post("/cases")
def create_case(body: CaseIn, db: Session = Depends(get_db)):
    case = models.Case(title=body.title)
    db.add(case)
    db.commit()
    return {"id": case.id, "title": case.title}


@router.get("/cases")
def list_cases(db: Session = Depends(get_db)):
    cases = db.scalars(select(models.Case).order_by(models.Case.id)).all()
    return [{"id": c.id, "title": c.title,
             "documents": len(c.documents),
             "conditions": len([x for x in c.conditions if x.status != "suggested"]),
             "suggested": len([x for x in c.conditions if x.status == "suggested"])}
            for c in cases]


@router.get("/cases/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = db.get(models.Case, case_id)
    if not case:
        raise HTTPException(404)
    return {"id": case.id, "title": case.title,
            "documents": [{"id": d.id, "filename": d.filename,
                           "doc_type": d.doc_type, "status": d.status,
                           "page_count": d.page_count} for d in case.documents]}


@router.get("/cases/{case_id}/profile")
def get_profile(case_id: int, db: Session = Depends(get_db)):
    row = db.scalars(select(models.ClaimantProfile)
                     .where(models.ClaimantProfile.case_id == case_id)).first()
    data = schemas.ClaimantProfileData.model_validate(row.data if row else {})
    return data.model_dump()


@router.put("/cases/{case_id}/profile")
def put_profile(case_id: int, body: schemas.ClaimantProfileData,
                db: Session = Depends(get_db)):
    if not db.get(models.Case, case_id):
        raise HTTPException(404)
    row = db.scalars(select(models.ClaimantProfile)
                     .where(models.ClaimantProfile.case_id == case_id)).first()
    if row is None:
        row = models.ClaimantProfile(case_id=case_id)
        db.add(row)
    row.data = body.model_dump()
    db.commit()
    return {"ok": True}


@router.post("/cases/{case_id}/profile/prefill")
def prefill_profile(case_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Case, case_id):
        raise HTTPException(404)
    job_id = enqueue("profile_prefill", {"case_id": case_id})
    return {"job_id": job_id}
