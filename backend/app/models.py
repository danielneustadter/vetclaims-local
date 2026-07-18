from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Case(Base):
    __tablename__ = "case"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), default="My VA Claim")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

    documents: Mapped[list[Document]] = relationship(back_populates="case")
    conditions: Mapped[list[Condition]] = relationship(back_populates="case")


class Document(Base):
    __tablename__ = "document"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("case.id"))
    filename: Mapped[str] = mapped_column(String(400))
    stored_path: Mapped[str] = mapped_column(String(600))
    sha256: Mapped[str] = mapped_column(String(64))
    doc_type: Mapped[str] = mapped_column(String(40), default="unknown")
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="uploaded")  # uploaded|extracting|ready|error
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)

    case: Mapped[Case] = relationship(back_populates="documents")
    pages: Mapped[list[Page]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "page"
    __table_args__ = (UniqueConstraint("document_id", "page_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"))
    page_no: Mapped[int] = mapped_column(Integer)  # 1-based
    text: Mapped[str] = mapped_column(Text, default="")
    text_source: Mapped[str] = mapped_column(String(10), default="native")  # native|ocr|none

    document: Mapped[Document] = relationship(back_populates="pages")


class ClaimantProfile(Base):
    """One per case; 21-526EZ-shaped fields stored as a JSON blob validated by
    schemas.ClaimantProfileData."""

    __tablename__ = "claimant_profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("case.id"), unique=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class Condition(Base):
    __tablename__ = "condition"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("case.id"))
    name: Mapped[str] = mapped_column(String(300))
    # how it relates to service, mirroring 526EZ section V options
    basis: Mapped[str] = mapped_column(String(20), default="direct")  # direct|secondary|presumptive|increase
    secondary_to: Mapped[str | None] = mapped_column(String(300), nullable=True)
    onset_date: Mapped[str | None] = mapped_column(String(20), nullable=True)  # YYYY-MM or YYYY-MM-DD
    exposure: Mapped[str | None] = mapped_column(String(200), nullable=True)  # e.g. burn pits
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="selected")  # suggested|selected|claimed|granted|denied
    sort: Mapped[int] = mapped_column(Integer, default=0)

    case: Mapped[Case] = relationship(back_populates="conditions")


class MedicalEvent(Base):
    """One extracted clinical fact with page-level provenance — the atom of
    the case database. Everything downstream (suggestions, drafts, grounding)
    cites these rows."""

    __tablename__ = "medical_event"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("case.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"))
    page_no: Mapped[int] = mapped_column(Integer)
    date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # diagnosis|complaint|injury|treatment|exposure|referral
    condition: Mapped[str] = mapped_column(String(300))  # normalized condition/topic name
    detail: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(200), default="")


class ExistingRating(Base):
    __tablename__ = "existing_rating"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("case.id"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("document.id"), nullable=True)
    condition: Mapped[str] = mapped_column(String(300))
    percent: Mapped[int] = mapped_column(Integer)
    diagnostic_code: Mapped[str] = mapped_column(String(10), default="")
    effective_date: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Chunk(Base):
    """Embedded text chunk; vectors live in the vec_chunk sqlite-vec table
    keyed by this row's id."""

    __tablename__ = "chunk"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("case.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("document.id"))
    page_start: Mapped[int] = mapped_column(Integer)
    page_end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class Job(Base):
    __tablename__ = "job"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|done|error
    progress: Mapped[str] = mapped_column(String(300), default="")
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
