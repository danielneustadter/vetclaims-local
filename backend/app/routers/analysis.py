from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..analysis.suggest import analyze
from ..db import get_db

router = APIRouter(prefix="/api", tags=["analysis"])


@router.get("/cases/{case_id}/analysis")
def get_analysis(case_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Case, case_id):
        raise HTTPException(404)
    return analyze(db, case_id)
