import datetime as dt

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..db import get_db
from ..extract.decisions import recommend
from ..llm.queue import enqueue
from ..packet.appeals import fill_appeal

router = APIRouter(prefix="/api", tags=["appeals"])


@router.post("/documents/{doc_id}/parse-decision")
def parse_decision(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(models.Document, doc_id)
    if not doc:
        raise HTTPException(404)
    if doc.status != "ready":
        raise HTTPException(400, "document text not extracted yet")
    return {"job_id": enqueue("parse_decision", {"document_id": doc_id})}


@router.get("/cases/{case_id}/decision")
def get_decision(case_id: int, db: Session = Depends(get_db)):
    issues = db.scalars(select(models.DecisionIssue)
                        .where(models.DecisionIssue.case_id == case_id)
                        .order_by(models.DecisionIssue.id)).all()
    return {
        "issues": [{"id": i.id, "condition": i.condition, "outcome": i.outcome,
                    "percent": i.percent, "effective_date": i.effective_date,
                    "reason": i.reason, "decision_date": i.decision_date,
                    "document_id": i.document_id} for i in issues],
        "recommendations": recommend(list(issues)),
    }


class AppealRequest(BaseModel):
    issue_ids: list[int]


@router.post("/cases/{case_id}/appeals/{form}")
def generate_appeal(case_id: int, form: str, body: AppealRequest,
                    db: Session = Depends(get_db)):
    if form not in ("20-0995", "20-0996"):
        raise HTTPException(400, "form must be 20-0995 or 20-0996 (10182 must "
                                 "be completed at va.gov/board-appeals)")
    issues = [i for i in db.scalars(
        select(models.DecisionIssue)
        .where(models.DecisionIssue.case_id == case_id,
               models.DecisionIssue.id.in_(body.issue_ids)))]
    if not issues:
        raise HTTPException(400, "no issues selected")
    row = db.scalars(select(models.ClaimantProfile)
                     .where(models.ClaimantProfile.case_id == case_id)).first()
    profile = schemas.ClaimantProfileData.model_validate(row.data if row else {})
    pdf = fill_appeal(form, profile, issues)
    out_dir = settings.output_dir / str(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{dt.date.today().isoformat()}_VA-{form}-draft.pdf"
    (out_dir / fname).write_bytes(pdf)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


class RebuttalRequest(BaseModel):
    issue_id: int


@router.post("/cases/{case_id}/rebuttal")
def draft_rebuttal(case_id: int, body: RebuttalRequest,
                   db: Session = Depends(get_db)):
    issue = db.get(models.DecisionIssue, body.issue_id)
    if not issue or issue.case_id != case_id:
        raise HTTPException(404)
    return {"job_id": enqueue("draft_rebuttal", {"issue_id": issue.id})}
