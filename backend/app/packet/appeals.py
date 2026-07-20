"""Fill AMA appeal forms: 20-0996 (Higher-Level Review) and 20-0995
(Supplemental Claim). Field names resolved against the live template field
list by suffix so minor form revisions don't hard-break the fill."""

from __future__ import annotations

from pypdf import PdfReader

from .. import models
from ..schemas import ClaimantProfileData
from .builders import _date_parts, _phone_parts, _ssn_parts, _zip_parts
from .fill import TEMPLATES, fill_form

TEMPLATES["20-0996"] = TEMPLATES["21-526EZ"].parent / "vba-20-0996.pdf"
TEMPLATES["20-0995"] = TEMPLATES["21-526EZ"].parent / "vba-20-0995.pdf"

_FIELD_CACHE: dict[str, list[str]] = {}


def _fields(form: str) -> list[str]:
    if form not in _FIELD_CACHE:
        _FIELD_CACHE[form] = list(PdfReader(str(TEMPLATES[form])).get_fields() or {})
    return _FIELD_CACHE[form]


def _find(form: str, suffix: str, nth: int = 0) -> str | None:
    hits = [n for n in _fields(form) if n.endswith(suffix)]
    return hits[nth] if len(hits) > nth else None


def _put(text: dict, form: str, suffix: str, value: str, nth: int = 0) -> None:
    if not value:
        return
    name = _find(form, suffix, nth)
    if name:
        text[name] = value


def _identity_block(form: str, p: ClaimantProfileData,
                    name_fields: dict[str, str]) -> dict[str, str]:
    text: dict[str, str] = {}
    _put(text, form, name_fields["first"], p.identity.first_name)
    _put(text, form, name_fields["mi"], p.identity.middle_initial[:1])
    _put(text, form, name_fields["last"], p.identity.last_name)
    s1, s2, s3 = _ssn_parts(p.identity.ssn)
    _put(text, form, name_fields["ssn1"], s1)
    _put(text, form, name_fields["ssn2"], s2)
    _put(text, form, name_fields["ssn3"], s3)
    _put(text, form, "VAFileNumber[0]", p.identity.va_file_number)
    m, d, y = _date_parts(p.identity.date_of_birth)
    _put(text, form, name_fields["dobm"], m)
    _put(text, form, name_fields["dobd"], d)
    _put(text, form, name_fields["doby"], y)
    c = p.contact
    _put(text, form, "CurrentMailingAddress_NumberAndStreet[0]", c.street)
    _put(text, form, "CurrentMailingAddress_ApartmentOrUnitNumber[0]", c.apt)
    _put(text, form, "CurrentMailingAddress_City[0]", c.city)
    _put(text, form, "CurrentMailingAddress_StateOrProvince[0]", c.state)
    _put(text, form, "CurrentMailingAddress_Country[0]", c.country)
    z5, z4 = _zip_parts(c.zip_code)
    _put(text, form, "CurrentMailingAddress_ZIPOrPostalCode_FirstFiveNumbers[0]", z5)
    _put(text, form, "CurrentMailingAddress_ZIPOrPostalCode_LastFourNumbers[0]", z4)
    return text


def build_0996(p: ClaimantProfileData,
               issues: list[models.DecisionIssue]) -> tuple[dict, dict]:
    form = "20-0996"
    text = _identity_block(form, p, {
        "first": "Veterans_First_Name[0]", "mi": "Veterans_Middle_Initial1[0]",
        "last": "Veterans_Last_Name[0]",
        "ssn1": "Veterans_SocialSecurityNumber_FirstThreeNumbers[0]",
        "ssn2": "Veterans_SocialSecurityNumber_SecondTwoNumbers[0]",
        "ssn3": "Veterans_SocialSecurityNumber_LastFourNumbers[0]",
        "dobm": "DOBmonth[0]", "dobd": "DOBday[0]", "doby": "DOByear[0]"})
    a, mid, last = _phone_parts(p.contact.phone)
    _put(text, form, "Telephone_Number_Area_Code[0]", a)
    _put(text, form, "Telephone_Middle_Three_Numbers[0]", mid)
    _put(text, form, "Telephone_Last_Four_Numbers[0]", last)
    _put(text, form, "E_Mail_Address_Optional[0]", p.contact.email)

    # issue rows: SPECIFICISSUE1[0..3] then SPECIFICISSUE3/4/5; decision
    # dates align Date_Month/Day/Year[0..]
    row_fields = (["SPECIFICISSUE1[0]", "SPECIFICISSUE1[1]", "SPECIFICISSUE1[2]",
                   "SPECIFICISSUE1[3]", "SPECIFICISSUE3[0]", "SPECIFICISSUE4[0]",
                   "SPECIFICISSUE5[0]"])
    for i, issue in enumerate(issues[:len(row_fields)]):
        _put(text, form, row_fields[i], issue.condition[:80])
        m, d, y = _date_parts(issue.decision_date or "")
        _put(text, form, f"Date_Month[{i}]", m)
        _put(text, form, f"Date_Day[{i}]", d)
        _put(text, form, f"Date_Year[{i}]", y)

    checks = {}
    benefit = _find(form, "RadioButtonList[0]")
    if benefit:
        checks[benefit] = "0"  # COMPENSATION (decoded via label correlation)
    return text, checks


def build_0995(p: ClaimantProfileData,
               issues: list[models.DecisionIssue]) -> tuple[dict, dict]:
    form = "20-0995"
    text = _identity_block(form, p, {
        "first": "VeteransFirstName[0]", "mi": "VeteransMiddleInitial1[0]",
        "last": "VeteransLastName[0]",
        "ssn1": "VeteransSocialSecurityNumber_FirstThreeNumbers[0]",
        "ssn2": "VeteransSocialSecurityNumber_SecondTwoNumbers[0]",
        "ssn3": "VeteransSocialSecurityNumber_LastFourNumbers[0]",
        "dobm": "VeteranDOBMonth[0]", "dobd": "VeteranDOBDay[0]",
        "doby": "VeteranDOBYear[0]"})
    _put(text, form, "Email[0]", p.contact.email)

    # Table2 rows: Row1 SPECIFICISSUE1[0], Row2.. SPECIFICISSUE2[0] per row
    rows = [n for n in _fields(form) if "Table2[0].Row" in n and "SPECIFICISSUE" in n]
    rows.sort(key=lambda n: n.split("Row")[1].split("[")[0].zfill(2))
    for i, issue in enumerate(issues[: len(rows)]):
        text[rows[i]] = issue.condition[:80]
        # fill any date fields living in the same row container
        row_prefix = rows[i].rsplit(".", 1)[0]
        for n in _fields(form):
            if n.startswith(row_prefix) and n != rows[i]:
                if "Month" in n:
                    text[n] = _date_parts(issue.decision_date or "")[0]
                elif "Day" in n:
                    text[n] = _date_parts(issue.decision_date or "")[1]
                elif "Year" in n:
                    text[n] = _date_parts(issue.decision_date or "")[2]

    checks = {}
    benefit = _find(form, "RadioButtonList[0]")
    if benefit:
        checks[benefit] = "0"  # COMPENSATION
    text = {k: v for k, v in text.items() if v}
    return text, checks


def fill_appeal(form: str, p: ClaimantProfileData,
                issues: list[models.DecisionIssue]) -> bytes:
    if form == "20-0996":
        text, checks = build_0996(p, issues)
    elif form == "20-0995":
        text, checks = build_0995(p, issues)
    else:
        raise ValueError(f"unsupported appeal form {form!r}")
    return fill_form(form, text, checks)
