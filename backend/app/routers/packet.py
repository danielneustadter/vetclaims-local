import datetime as dt
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import settings
from ..db import get_db
from ..packet import builders, fill

router = APIRouter(prefix="/api", tags=["packet"])


def _profile(db: Session, case_id: int) -> schemas.ClaimantProfileData:
    row = db.scalars(select(models.ClaimantProfile)
                     .where(models.ClaimantProfile.case_id == case_id)).first()
    return schemas.ClaimantProfileData.model_validate(row.data if row else {})


def _selected_conditions(db: Session, case_id: int) -> list[models.Condition]:
    return list(db.scalars(
        select(models.Condition)
        .where(models.Condition.case_id == case_id,
               models.Condition.status.in_(["selected", "claimed"]))
        .order_by(models.Condition.sort, models.Condition.id)))


def _save_and_respond(case_id: int, name: str, pdf: bytes) -> Response:
    out_dir = settings.output_dir / str(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.date.today().isoformat()
    fname = f"{stamp}_{name}"
    (out_dir / fname).write_bytes(pdf)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.post("/cases/{case_id}/forms/21-526EZ")
def generate_526ez(case_id: int, db: Session = Depends(get_db)):
    profile = _profile(db, case_id)
    conditions = _selected_conditions(db, case_id)
    if not conditions:
        raise HTTPException(400, "no selected conditions — add or select conditions first")
    text, checks = builders.build_526ez(profile, conditions)
    pdf = fill.fill_form("21-526EZ", text, checks)
    return _save_and_respond(case_id, "VA-21-526EZ-draft.pdf", pdf)


class StatementIn(BaseModel):
    statement: str
    label: str = "statement"


@router.post("/cases/{case_id}/forms/21-4138")
def generate_4138(case_id: int, body: StatementIn, db: Session = Depends(get_db)):
    if not body.statement.strip():
        raise HTTPException(400, "statement text is empty")
    profile = _profile(db, case_id)
    text, checks = builders.build_4138(profile, body.statement)
    pdf = fill.fill_form("21-4138", text, checks)
    label = re.sub(r"[^A-Za-z0-9_-]", "-", body.label)[:40] or "statement"
    return _save_and_respond(case_id, f"VA-21-4138-{label}-draft.pdf", pdf)


@router.post("/cases/{case_id}/forms/21-0966")
def generate_0966(case_id: int, db: Session = Depends(get_db)):
    profile = _profile(db, case_id)
    text, checks = builders.build_0966(profile)
    pdf = fill.fill_form("21-0966", text, checks)
    return _save_and_respond(case_id, "VA-21-0966-ITF-draft.pdf", pdf)


@router.post("/cases/{case_id}/packet")
def build_packet(case_id: int, db: Session = Depends(get_db)):
    from ..packet.assemble import build_packet_zip
    try:
        blob = build_packet_zip(db, case_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    out_dir = settings.output_dir / str(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{dt.date.today().isoformat()}_VA-claim-packet.zip"
    (out_dir / fname).write_bytes(blob)
    return Response(content=blob, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/forms/{form}/preview/{page_no}")
def preview_blank(form: str, page_no: int):
    if form not in fill.TEMPLATES:
        raise HTTPException(404)
    png = fill.render_page_png(fill.TEMPLATES[form].read_bytes(), page_no)
    return Response(content=png, media_type="image/png")
