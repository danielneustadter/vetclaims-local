"""Form-fill smoke tests. All data is fictional (see NFR5)."""

from types import SimpleNamespace

from pypdf import PdfReader
import io

from app.packet import builders, fill
from app.schemas import (ClaimantProfileData, ContactInfo, ServiceInfo,
                         ServicePeriod, VeteranIdentity)

FICTIONAL = ClaimantProfileData(
    identity=VeteranIdentity(
        first_name="Alexandra", middle_initial="J", last_name="Testcase",
        ssn="000-12-3456", va_file_number="C-00-000-000",
        date_of_birth="1988-04-15"),
    contact=ContactInfo(
        phone="555-000-1234", email="alex.testcase@example.com",
        street="123 Liberty Lane", city="Springfield", state="VA",
        zip_code="22150"),
    service=ServiceInfo(
        periods=[ServicePeriod(branch="Army", entry_date="2006-06-01",
                               separation_date="2014-09-30")],
        exposures=["burn pits", "asbestos"]),
)

CONDITIONS = [
    SimpleNamespace(name="Tinnitus", basis="direct", secondary_to=None,
                    onset_date="2010-03", exposure="Weapons/aircraft noise",
                    notes=""),
    SimpleNamespace(name="Sleep apnea", basis="secondary",
                    secondary_to="PTSD", onset_date="2015-01", exposure=None,
                    notes=""),
    SimpleNamespace(name="Chronic rhinitis", basis="presumptive",
                    secondary_to=None, onset_date="2012-07",
                    exposure="Burn pit / airborne hazards (PACT Act)", notes=""),
]


def _field_values(pdf: bytes) -> dict:
    fields = PdfReader(io.BytesIO(pdf)).get_fields() or {}
    return {k: f.get("/V") for k, f in fields.items()}


def test_526ez_fill():
    text, checks = builders.build_526ez(FICTIONAL, CONDITIONS)
    pdf = fill.fill_form("21-526EZ", text, checks)
    vals = _field_values(pdf)
    assert vals["F[0].Page_10[0].Veteran_Service_Member_First_Name[0]"] == "Alexandra"
    assert vals["F[0].Page_10[0].SocialSecurityNumber_FirstThreeNumbers[0]"] == "000"
    assert vals["F[0].#subform[10].CURRENTDISABILITY[0]"] == "Tinnitus"
    assert vals["F[0].#subform[10].CURRENTDISABILITY[1]"] == "Sleep apnea"
    assert "Secondary to PTSD" in str(
        vals["F[0].#subform[10].Specify_Type_Of_Exposure_Event_Or_Injury[1]"])
    assert vals["F[0].#subform[11].EntryDate_Year[0]"] == "2006"
    assert str(vals["F[0].Page_10[0].FULLY_DEVELOPED_CLAIM_FDC_PROGRAM[0]"]) == "/1"
    # burn pits (no dedicated checkbox) lands in Other; asbestos has its own box
    assert str(vals["F[0].#subform[9].ASBESTOS[0]"]) == "/1"


def test_4138_fill_short_and_long():
    text, _ = builders.build_4138(FICTIONAL, "Short fictional statement.")
    vals = _field_values(fill.fill_form("21-4138", text, {}))
    assert vals["form1[0].#subform[0].REMARKS[0]"] == "Short fictional statement."

    long_stmt = ("This is a fictional statement. " * 120).strip()
    text, _ = builders.build_4138(FICTIONAL, long_stmt)
    vals = _field_values(fill.fill_form("21-4138", text, {}))
    assert "(CONTINUED ON PAGE 2)" in vals["form1[0].#subform[0].REMARKS[0]"]
    assert vals["form1[0].#subform[1].REMARKS[1]"]


def test_0966_fill():
    text, _ = builders.build_0966(FICTIONAL)
    vals = _field_values(fill.fill_form("21-0966", text, {}))
    assert vals["form1[0].#subform[0].VeteransFirstName[0]"] == "Alexandra"
    assert vals["form1[0].#subform[0].LastFourNumbers[0]"] == "3456"   # SSN last-4
    assert vals["form1[0].#subform[0].LastFourNumbers[1]"] == "1234"   # phone last-4


def test_render_preview():
    text, checks = builders.build_526ez(FICTIONAL, CONDITIONS)
    pdf = fill.fill_form("21-526EZ", text, checks)
    png = fill.render_page_png(pdf, 10)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
