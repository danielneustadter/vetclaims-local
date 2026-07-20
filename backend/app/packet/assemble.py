"""Full filing-packet assembly: checklist cover + ITF + 526EZ + statement
4138s + indexed evidence PDF, zipped for download."""

from __future__ import annotations

import datetime as dt
import io
import zipfile

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy import select

from .. import models, schemas
from . import builders, evidence, fill

W, H = letter


def _checklist_pdf(profile: schemas.ClaimantProfileData,
                   conditions: list[models.Condition],
                   n_statements: int, itf_date: str | None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.setFillColor(HexColor("#1b2a4a"))
    c.setFont("Helvetica-Bold", 17)
    c.drawString(54, H - 64, "VA Disability Claim — Filing Checklist")
    c.setFillColor(HexColor("#444444"))
    c.setFont("Helvetica", 9)
    name = f"{profile.identity.first_name} {profile.identity.last_name}".strip()
    c.drawString(54, H - 82, f"Prepared {dt.date.today().isoformat()} for {name or 'the veteran'} "
                             "with VetClaims Local (self-hosted).")
    y = H - 112

    def line(txt, bold=False, indent=0, color="#000000", dy=15):
        nonlocal y
        c.setFillColor(HexColor(color))
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        c.drawString(54 + indent, y, txt)
        y -= dy

    line("What is in this packet", bold=True)
    line("[  ] VA Form 21-0966 — Intent to File (file FIRST if you have not already)", indent=12)
    line(f"[  ] VA Form 21-526EZ — claiming {len(conditions)} condition(s)", indent=12)
    line(f"[  ] {n_statements} personal statement(s) on VA Form 21-4138", indent=12)
    line("[  ] Evidence packet with per-condition index and exhibit stamps", indent=12)
    y -= 6
    line("Conditions being claimed", bold=True)
    for cond in conditions:
        basis = {"direct": "direct", "secondary": f"secondary to {cond.secondary_to}",
                 "presumptive": f"presumptive ({cond.exposure or 'exposure'})",
                 "increase": "increase"}.get(cond.basis, cond.basis)
        line(f"• {cond.name} — {basis}", indent=12)
    y -= 6
    line("Before you file — in this order", bold=True)
    steps = [
        "1. Read every page of every form. Fix anything wrong — this software drafts, you decide.",
        f"2. Intent to File: {'on record since ' + itf_date + ' — your effective date is protected.' if itf_date else 'submit the 21-0966 (or file online at VA.gov, which sets ITF automatically).'}",
        "3. Sign the 21-526EZ in Section IX and each 21-4138 where indicated. Unsigned forms are returned.",
        "4. File at VA.gov (upload), by mail to the Evidence Intake Center, or through a free accredited VSO.",
        "5. Keep this entire packet. Note your submission confirmation number and date.",
        "6. Expect a C&P exam letter — use your prep sheets; attend or reschedule, never no-show.",
    ]
    for s in steps:
        line(s, indent=12, dy=16)
    y -= 8
    line("Important", bold=True, color="#b00020")
    for s in [
        "VetClaims Local is not the VA, not a law firm, and not an accredited representative.",
        "Nothing in this packet is legal or medical advice. AI-assisted drafts can contain errors.",
        "Free help exists: VA-accredited VSOs (DAV, VFW, American Legion, county service officers).",
    ]:
        line(s, indent=12, color="#b00020", dy=14)
    c.showPage()
    c.save()
    return buf.getvalue()


def build_packet_zip(db, case_id: int) -> bytes:
    profile_row = db.scalars(select(models.ClaimantProfile)
                             .where(models.ClaimantProfile.case_id == case_id)).first()
    profile = schemas.ClaimantProfileData.model_validate(
        profile_row.data if profile_row else {})
    conditions = list(db.scalars(
        select(models.Condition)
        .where(models.Condition.case_id == case_id,
               models.Condition.status.in_(["selected", "claimed"]))
        .order_by(models.Condition.sort, models.Condition.id)))
    if not conditions:
        raise ValueError("no selected conditions")

    statements = db.scalars(
        select(models.Draft).where(models.Draft.case_id == case_id,
                                   models.Draft.kind == "personal_statement")).all()

    text, checks = builders.build_526ez(profile, conditions)
    pdf_526 = fill.fill_form("21-526EZ", text, checks)
    text, checks = builders.build_0966(profile)
    pdf_0966 = fill.fill_form("21-0966", text, checks)

    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("01_Filing_Checklist.pdf",
                   _checklist_pdf(profile, conditions, len(statements),
                                  getattr(profile, "itf_date", "") or None))
        z.writestr("02_VA-21-0966_Intent_to_File.pdf", pdf_0966)
        z.writestr("03_VA-21-526EZ_Claim.pdf", pdf_526)
        for i, d in enumerate(statements, start=1):
            text, _ = builders.build_4138(profile, d.content)
            label = (d.title.replace("Personal statement — ", "")
                     .replace(" ", "-")[:40])
            safe = "".join(ch for ch in label if ch.isalnum() or ch in "-_")
            z.writestr(f"04_{i:02d}_VA-21-4138_{safe}.pdf",
                       fill.fill_form("21-4138", text, {}))
        z.writestr("05_Evidence_Packet.pdf",
                   evidence.build_evidence_pdf(db, case_id))
    return zbuf.getvalue()
