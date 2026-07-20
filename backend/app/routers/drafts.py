from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..drafting import generate
from ..llm.queue import enqueue

router = APIRouter(prefix="/api", tags=["drafts"])


def _out(d: models.Draft) -> dict:
    return {"id": d.id, "case_id": d.case_id, "condition_id": d.condition_id,
            "kind": d.kind, "title": d.title, "content": d.content,
            "grounding": d.grounding,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None}


@router.get("/cases/{case_id}/drafts")
def list_drafts(case_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(models.Draft).where(models.Draft.case_id == case_id)
                      .order_by(models.Draft.id.desc())).all()
    return [_out(d) for d in rows]


class DraftRequest(BaseModel):
    condition_id: int
    kind: str  # personal_statement|nexus_outline|cp_prep|lay_template


@router.post("/cases/{case_id}/drafts")
def create_draft(case_id: int, body: DraftRequest, db: Session = Depends(get_db)):
    condition = db.get(models.Condition, body.condition_id)
    if not condition or condition.case_id != case_id:
        raise HTTPException(404, "condition not found")

    if body.kind == "personal_statement":  # LLM + grounding check → job
        return {"job_id": enqueue("draft_statement",
                                  {"condition_id": body.condition_id})}

    profile_row = db.scalars(select(models.ClaimantProfile)
                             .where(models.ClaimantProfile.case_id == case_id)).first()
    profile = schemas.ClaimantProfileData.model_validate(
        profile_row.data if profile_row else {})
    name = f"{profile.identity.first_name} {profile.identity.last_name}".strip() or "the veteran"

    if body.kind == "nexus_outline":
        content = generate.nexus_outline(db, condition, case_id)
        title = f"Nexus letter outline — {condition.name}"
    elif body.kind == "cp_prep":
        content = generate.cp_prep(condition)
        title = f"C&P exam prep — {condition.name}"
    elif body.kind == "lay_template":
        content = generate.lay_template(condition, name)
        title = f"Lay statement template — {condition.name}"
    else:
        raise HTTPException(400, f"unknown draft kind {body.kind!r}")

    draft = models.Draft(case_id=case_id, condition_id=condition.id,
                         kind=body.kind, title=title, content=content)
    db.add(draft)
    db.commit()
    return {"draft": _out(draft)}


class DraftUpdate(BaseModel):
    content: str


@router.put("/drafts/{draft_id}")
def update_draft(draft_id: int, body: DraftUpdate, db: Session = Depends(get_db)):
    d = db.get(models.Draft, draft_id)
    if not d:
        raise HTTPException(404)
    d.content = body.content
    db.commit()
    return _out(d)


@router.delete("/drafts/{draft_id}")
def delete_draft(draft_id: int, db: Session = Depends(get_db)):
    d = db.get(models.Draft, draft_id)
    if not d:
        raise HTTPException(404)
    db.delete(d)
    db.commit()
    return {"ok": True}
