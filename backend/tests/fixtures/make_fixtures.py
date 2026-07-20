"""Generate fictional test-fixture PDFs (a mini STR set + DD-214 summary).
Every page is headed FICTIONAL RECORD so output can never be mistaken for a
real document. Usage: python -m tests.fixtures.make_fixtures <out_dir>"""

import sys
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

W, H = letter

VET = "TESTCASE, ALEXANDRA J    SSN 000-12-3456    DOB 1988-04-15"

STR_PAGES = [
    ("CHRONOLOGICAL RECORD OF MEDICAL CARE — 2010-03-22, Fort Liberty NC", [
        "CC: Ringing in both ears x 3 weeks.",
        "HPI: SPC Testcase reports constant bilateral tinnitus following M240",
        "range qualification 2010-03-01 without adequate hearing protection.",
        "High-pitched ringing, worse at night, interferes with sleep onset.",
        "A: Bilateral tinnitus, noise-induced. Audiology referral placed.",
        "P: Hearing conservation counseling. Follow up PRN.",
    ]),
    ("CHRONOLOGICAL RECORD OF MEDICAL CARE — 2011-08-14, Fort Liberty NC", [
        "CC: Right knee pain after unit PT.",
        "HPI: Twisting injury during formation run on uneven terrain 2011-08-12.",
        "Swelling, pain 6/10 on stairs. McMurray positive.",
        "A: Right knee medial meniscus strain.",
        "P: Profile 14 days, NSAIDs, PT referral. MRI if not improved.",
    ]),
    ("POST-DEPLOYMENT HEALTH ASSESSMENT — 2012-11-05, Joint Base Balad IZ", [
        "Deployment: Joint Base Balad, Iraq, 2012-02 to 2012-11.",
        "Member reports daily exposure to open-air burn pit smoke near billeting.",
        "Reports recurrent cough, nasal congestion, and sinus pressure since June.",
        "A: Chronic rhinitis, suspect airborne-hazard related.",
        "P: ENT follow-up at home station. Exposure documented in DOEHRS.",
    ]),
    ("BEHAVIORAL HEALTH NOTE — 2013-04-19, Fort Liberty NC", [
        "CC: Poor sleep, irritability since redeployment.",
        "HPI: Reports nightmares 2-3x/week, hypervigilance in crowds,",
        "avoidance of fireworks. Onset following 2012 Iraq deployment.",
        "A: Adjustment disorder; rule out PTSD. PCL-5 score 41.",
        "P: Referred to behavioral health clinic for evaluation.",
    ]),
]

DD214_LINES = [
    "1. NAME: TESTCASE, ALEXANDRA J          2. DEPARTMENT: ARMY",
    "3. SSN: 000-12-3456                     4. GRADE: SGT / E-5",
    "12a. DATE ENTERED AD THIS PERIOD: 2006-06-01",
    "12b. SEPARATION DATE THIS PERIOD: 2014-09-30",
    "13. DECORATIONS: ARCOM (2), AAM, IRAQ CAMPAIGN MEDAL W/ CAMPAIGN STAR",
    "18. REMARKS: SERVICE IN IRAQ 2012-02-10 TO 2012-11-20 // ",
    "    IMMINENT DANGER PAY AREA // HONORABLE",
    "24. CHARACTER OF SERVICE: HONORABLE",
    "28. NARRATIVE REASON FOR SEPARATION: COMPLETION OF REQUIRED SERVICE",
]


def _page_header(c, title):
    c.setFillColor(HexColor("#b00020"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(W / 2, H - 30,
                        "FICTIONAL RECORD — SOFTWARE TEST FIXTURE — NOT A REAL PERSON")
    c.setFillColor(HexColor("#000000"))
    c.setFont("Helvetica-Bold", 11)
    c.drawString(54, H - 60, title)
    c.setFont("Helvetica", 9)
    c.drawString(54, H - 76, VET)
    c.line(54, H - 82, W - 54, H - 82)


def make_str(path: Path):
    c = canvas.Canvas(str(path), pagesize=letter)
    for title, lines in STR_PAGES:
        _page_header(c, title)
        c.setFont("Courier", 10)
        y = H - 110
        for ln in lines:
            c.drawString(54, y, ln)
            y -= 16
        c.showPage()
    c.save()


def make_dd214(path: Path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _page_header(c, "CERTIFICATE OF RELEASE OR DISCHARGE FROM ACTIVE DUTY (DD-214 STYLE SUMMARY)")
    c.setFont("Courier", 10)
    y = H - 110
    for ln in DD214_LINES:
        c.drawString(54, y, ln)
        y -= 18
    c.showPage()
    c.save()


RATING_LINES = [
    "DEPARTMENT OF VETERANS AFFAIRS — RATING DECISION (FICTIONAL)",
    "",
    "Veteran: TESTCASE, ALEXANDRA J    File: C00000000",
    "",
    "DECISION",
    "1. Service connection for tinnitus is granted with an evaluation of",
    "   10 percent effective 2015-01-01. (Diagnostic Code 6260)",
    "2. Service connection for right knee strain is granted with an",
    "   evaluation of 10 percent effective 2015-01-01. (Diagnostic Code 5257)",
    "",
    "COMBINED EVALUATION FOR COMPENSATION: 20% from 2015-01-01",
]


def make_rating_decision(path: Path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _page_header(c, "VA RATING DECISION (FICTIONAL TEST FIXTURE)")
    c.setFont("Courier", 10)
    y = H - 110
    for ln in RATING_LINES:
        c.drawString(54, y, ln)
        y -= 16
    c.showPage()
    c.save()


def make_scanned_str(path: Path):
    """A page with NO text layer (rendered to an image) to exercise OCR."""
    import io

    from PIL import Image, ImageDraw

    img = Image.new("L", (1700, 2200), 255)
    d = ImageDraw.Draw(img)
    lines = [
        "FICTIONAL RECORD - SOFTWARE TEST FIXTURE - NOT A REAL PERSON",
        "",
        "CHRONOLOGICAL RECORD OF MEDICAL CARE  2013-09-02  FORT LIBERTY NC",
        "TESTCASE, ALEXANDRA J   SSN 000-12-3456",
        "",
        "CC: Low back pain after ruck march.",
        "HPI: SGT Testcase reports lumbar pain 5/10 after 12-mile ruck",
        "with 45 lb load on 2013-08-30. Pain radiates to right hip.",
        "A: Lumbar strain, mechanical low back pain.",
        "P: Quarters 24h, NSAIDs, core strengthening handout.",
    ]
    y = 120
    for ln in lines:
        d.text((110, y), ln, fill=0, font_size=44)
        y += 70
    buf = io.BytesIO()
    img.save(buf, format="PNG", dpi=(200, 200))

    import fitz
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(fitz.Rect(0, 0, 612, 792), stream=buf.getvalue())
    doc.save(str(path))
    doc.close()


DECISION_LINES = [
    "DEPARTMENT OF VETERANS AFFAIRS (FICTIONAL TEST LETTER)",
    "Decision date: 2026-05-12",
    "",
    "Dear Ms. Testcase,",
    "",
    "We made a decision on your claim received 2026-01-15.",
    "",
    "DECISION",
    "1. Service connection for tinnitus is GRANTED with an evaluation of",
    "   10 percent effective 2026-01-15.",
    "2. Service connection for chronic rhinitis is DENIED. The evidence",
    "   shows in-service respiratory complaints, but there is no current",
    "   diagnosis of chronic rhinitis from a medical provider.",
    "3. Service connection for PTSD is DENIED because the evidence does not",
    "   show a confirmed diagnosis of PTSD under DSM-5 criteria.",
]


def make_decision_letter(path: Path):
    c = canvas.Canvas(str(path), pagesize=letter)
    _page_header(c, "VA DECISION LETTER (FICTIONAL TEST FIXTURE)")
    c.setFont("Courier", 10)
    y = H - 110
    for ln in DECISION_LINES:
        c.drawString(54, y, ln)
        y -= 16
    c.showPage()
    c.save()


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    make_str(out / "fixture_str_testcase.pdf")
    make_dd214(out / "fixture_dd214_testcase.pdf")
    make_rating_decision(out / "fixture_rating_decision_testcase.pdf")
    make_scanned_str(out / "fixture_scanned_str_testcase.pdf")
    make_decision_letter(out / "fixture_decision_letter_testcase.pdf")
    print(f"wrote fixtures to {out}")
