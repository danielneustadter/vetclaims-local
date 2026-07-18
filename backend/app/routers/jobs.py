from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..db import get_db

router = APIRouter(prefix="/api", tags=["jobs"])


def _job_out(j: models.Job) -> dict:
    return {"id": j.id, "type": j.type, "status": j.status,
            "progress": j.progress, "result": j.result,
            "error": (j.error or "").splitlines()[-1] if j.error else None}


@router.get("/jobs/{job_id}")
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if not job:
        raise HTTPException(404)
    return _job_out(job)


@router.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.scalars(select(models.Job).order_by(models.Job.id.desc()).limit(25)).all()
    return [_job_out(j) for j in jobs]
