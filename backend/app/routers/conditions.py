from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db

router = APIRouter(prefix="/api", tags=["conditions"])


@router.get("/cases/{case_id}/conditions")
def list_conditions(case_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(models.Condition)
                      .where(models.Condition.case_id == case_id)
                      .order_by(models.Condition.sort, models.Condition.id)).all()
    return [schemas.ConditionOut.model_validate(r).model_dump() for r in rows]


@router.post("/cases/{case_id}/conditions")
def add_condition(case_id: int, body: schemas.ConditionIn,
                  db: Session = Depends(get_db)):
    if not db.get(models.Case, case_id):
        raise HTTPException(404)
    row = models.Condition(case_id=case_id, **body.model_dump())
    db.add(row)
    db.commit()
    return schemas.ConditionOut.model_validate(row).model_dump()


@router.put("/conditions/{cond_id}")
def update_condition(cond_id: int, body: schemas.ConditionIn,
                     db: Session = Depends(get_db)):
    row = db.get(models.Condition, cond_id)
    if not row:
        raise HTTPException(404)
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    return schemas.ConditionOut.model_validate(row).model_dump()


@router.delete("/conditions/{cond_id}")
def delete_condition(cond_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Condition, cond_id)
    if not row:
        raise HTTPException(404)
    db.delete(row)
    db.commit()
    return {"ok": True}
