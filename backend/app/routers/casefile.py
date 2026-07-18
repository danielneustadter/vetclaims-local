from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db
from ..extract.case_extract import timeline
from ..ingest import embed
from ..llm.queue import enqueue

router = APIRouter(prefix="/api", tags=["casefile"])


@router.post("/cases/{case_id}/extract")
def run_extract(case_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Case, case_id):
        raise HTTPException(404)
    return {"job_id": enqueue("case_extract", {"case_id": case_id})}


@router.get("/cases/{case_id}/timeline")
def get_timeline(case_id: int, db: Session = Depends(get_db)):
    return timeline(db, case_id)


@router.get("/cases/{case_id}/ratings")
def get_ratings(case_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(models.ExistingRating)
                      .where(models.ExistingRating.case_id == case_id)).all()
    return [{"id": r.id, "condition": r.condition, "percent": r.percent,
             "diagnostic_code": r.diagnostic_code,
             "effective_date": r.effective_date} for r in rows]


@router.get("/cases/{case_id}/search")
def search_chunks(case_id: int, q: str = Query(min_length=2),
                  db: Session = Depends(get_db)):
    return embed.search(db, case_id, q)
