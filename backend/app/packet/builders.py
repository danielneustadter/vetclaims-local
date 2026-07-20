"""Map claimant profile + conditions onto official VA form field names.

Field names come from the templates' AcroForm dictionaries (see
docs/architecture.md D6). Ambiguous unlabeled radio groups (e.g. branch of
service, ITF benefit type) are intentionally left unfilled until the visual
field-verification pass; the veteran reviews every output before filing."""

from __future__ import annotations

import textwrap

from ..schemas import ClaimantProfileData

P10 = "F[0].Page_10[0]."
S9 = "F[0].#subform[9]."
S10 = "F[0].#subform[10]."
S11 = "F[0].#subform[11]."
S12 = "F[0].#subform[12]."
S13 = "F[0].#subform[13]."
S14 = "F[0].#subform[14]."

# SSN is repeated on every sheet of the 526EZ
_526_SSN = [
    (P10 + "SocialSecurityNumber_FirstThreeNumbers[0]",
     P10 + "SocialSecurityNumber_SecondTwoNumbers[0]",
     P10 + "SocialSecurityNumber_LastFourNumbers[0]"),
    (S9 + "SocialSecurityNumber_FirstThreeNumbers[0]",
     S9 + "SocialSecurityNumber_SecondTwoNumbers[0]",
     S9 + "SocialSecurityNumber_LastFourNumbers[0]"),
    (S10 + "SocialSecurityNumber_FirstThreeNumbers[1]",
     S10 + "SocialSecurityNumber_SecondTwoNumbers[1]",
     S10 + "SocialSecurityNumber_LastFourNumbers[1]"),
    (S11 + "SocialSecurityNumber_FirstThreeNumbers[2]",
     S11 + "SocialSecurityNumber_SecondTwoNumbers[2]",
     S11 + "SocialSecurityNumber_LastFourNumbers[2]"),
    (S12 + "SocialSecurityNumber_FirstThreeNumbers[3]",
     S12 + "SocialSecurityNumber_SecondTwoNumbers[3]",
     S12 + "SocialSecurityNumber_LastFourNumbers[3]"),
    (S13 + "SocialSecurityNumber_FirstThreeNumbers[4]",
     S13 + "SocialSecurityNumber_SecondTwoNumbers[4]",
     S13 + "SocialSecurityNumber_LastFourNumbers[4]"),
    (S14 + "SocialSecurityNumber_FirstThreeNumbers[5]",
     S14 + "SocialSecurityNumber_SecondTwoNumbers[5]",
     S14 + "SocialSecurityNumber_LastFourNumbers[5]"),
]

MAX_CONDITIONS = 15  # rows on sheet 5 (#subform[10]); overflow sheet comes later

# Radio-group state mappings decoded via widget-rect ↔ label correlation
# (scripts kept in repo history; verified by rendering). All on #subform[11]
# unless noted.
BRANCH_19A = {  # RadioButtonList[10]
    "army": "0", "air force": "1", "noaa": "2", "navy": "3",
    "coast guard": "4", "usphs": "5", "public health": "5",
    "marine": "6", "space force": "7",
}
COMPONENT_19B = {"active": "0", "reserve": "1", "national guard": "2"}  # RadioButtonList[12]

_YESNO_S11 = {  # two-state groups on #subform[11]: /0 = YES, /1 = NO
    "served_other_name": "RadioButtonList[0]",   # 18A
    "combat_since_911": "RadioButtonList[1]",    # 20C
    "reserve_ng_service": "RadioButtonList[2]",  # 21A
    "pow": "RadioButtonList[6]",                 # 23A
    "retired_pay": "RadioButtonList[7]",         # 24A
}

_EXPOSURE_CHECKBOXES = {
    "asbestos": S9 + "ASBESTOS[0]",
    "shad": S9 + "SHAD_Shipboard_Hazard_And_Defense[0]",
    "camp lejeune": S9 + "Contaminated_Water_At_Camp_Lejeune[0]",
    "mustard gas": S9 + "Mustard_Gas[0]",
    "radiation": S9 + "Radiation[0]",
    "mos": S9 + "Military_Occupational_Specialty_MOS_Related_Toxin[0]",
}


def _ssn_parts(ssn: str) -> tuple[str, str, str]:
    digits = "".join(c for c in ssn if c.isdigit())
    return (digits[0:3], digits[3:5], digits[5:9]) if len(digits) == 9 else ("", "", "")


def _date_parts(date: str) -> tuple[str, str, str]:
    """YYYY-MM-DD (or YYYY-MM / YYYY) → (month, day, year)."""
    bits = (date or "").split("-")
    y = bits[0] if bits and len(bits[0]) == 4 else ""
    m = bits[1] if len(bits) > 1 else ""
    d = bits[2] if len(bits) > 2 else ""
    return m, d, y


def _phone_parts(phone: str) -> tuple[str, str, str]:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return (digits[0:3], digits[3:6], digits[6:10]) if len(digits) == 10 else ("", "", "")


def _zip_parts(z: str) -> tuple[str, str]:
    digits = "".join(c for c in z if c.isdigit())
    return digits[0:5], digits[5:9]


def _condition_row_texts(cond) -> tuple[str, str, str]:
    """(disability name, exposure/event/injury type, relation explanation)."""
    if cond.basis == "secondary":
        rel = cond.secondary_to or "service-connected condition"
        return (cond.name, f"Secondary to {rel}",
                cond.notes or f"Caused or aggravated by my service-connected {rel}.")
    if cond.basis == "presumptive":
        exp = cond.exposure or "toxic exposure"
        return (cond.name, exp,
                cond.notes or f"Presumptive condition related to {exp} during qualifying service.")
    if cond.basis == "increase":
        return (cond.name, "Service-connected — increase",
                cond.notes or "Requesting increased evaluation; condition has worsened.")
    return (cond.name, cond.exposure or "In-service event/injury",
            cond.notes or "Condition began in and has continued since active service.")


def build_526ez(profile: ClaimantProfileData, conditions: list) -> tuple[dict, dict]:
    p = profile
    text: dict[str, str] = {}
    checks: dict[str, str] = {}

    # --- identity (sheet 1 / Page_10) ---
    text[P10 + "Veteran_Service_Member_First_Name[0]"] = p.identity.first_name
    text[P10 + "Veteran_Service_Member_Middle_Initial[0]"] = p.identity.middle_initial[:1]
    text[P10 + "Veteran_Service_Member_Last_Name[0]"] = p.identity.last_name
    text[P10 + "VA_File_Number[0]"] = p.identity.va_file_number
    text[P10 + "Veterans_Service_Number_If_Applicable[0]"] = p.identity.service_number
    m, d, y = _date_parts(p.identity.date_of_birth)
    text[P10 + "Date_Of_Birth_Month[0]"], text[P10 + "Date_Of_Birth_Day[0]"], \
        text[P10 + "Date_Of_Birth_Year[0]"] = m, d, y
    s1, s2, s3 = _ssn_parts(p.identity.ssn)
    for f1, f2, f3 in _526_SSN:
        text[f1], text[f2], text[f3] = s1, s2, s3

    # --- contact ---
    c = p.contact
    text[P10 + "CurrentMailingAddress_NumberAndStreet[0]"] = c.street
    text[P10 + "CurrentMailingAddress_ApartmentOrUnitNumber[0]"] = c.apt
    text[P10 + "CurrentMailingAddress_City[0]"] = c.city
    text[P10 + "CurrentMailingAddress_StateOrProvince[0]"] = c.state
    text[P10 + "CurrentMailingAddress_Country[0]"] = c.country
    z5, z4 = _zip_parts(c.zip_code)
    text[P10 + "CurrentMailingAddress_ZIPOrPostalCode_FirstFiveNumbers[0]"] = z5
    text[P10 + "CurrentMailingAddress_ZIPOrPostalCode_LastFourNumbers[0]"] = z4
    a, mid, last = _phone_parts(c.phone)
    text[P10 + "Daytime_Phone_Number_Area_Code[0]"] = a
    text[P10 + "Telephone_Middle_Three_Numbers[0]"] = mid
    text[P10 + "Telephone_Last_Four_Numbers[0]"] = last
    text[P10 + "Email_Address_Optional[0]"] = c.email

    # --- claim process ---
    if getattr(p, "claim_process", "FDC") == "FDC":
        checks[P10 + "FULLY_DEVELOPED_CLAIM_FDC_PROGRAM[0]"] = "1"
    else:
        checks[P10 + "Standard_Claim_Process[0]"] = "1"

    # --- toxic exposures (sheet 4 / #subform[9]) ---
    unmatched = []
    for exp in p.service.exposures:
        key = next((k for k in _EXPOSURE_CHECKBOXES if k in exp.lower()), None)
        if key:
            checks[_EXPOSURE_CHECKBOXES[key]] = "1"
        else:
            unmatched.append(exp)
    if unmatched:
        checks[S9 + "OTHER_Specify[2]"] = "1"
        text[S9 + "Other_Specify[0]"] = "; ".join(unmatched)[:100]

    # --- conditions table (sheet 5 / #subform[10]) ---
    rows = conditions[:MAX_CONDITIONS]
    for i, cond in enumerate(rows):
        name, exposure, explain = _condition_row_texts(cond)
        text[S10 + f"CURRENTDISABILITY[{i}]"] = name
        text[S10 + f"Specify_Type_Of_Exposure_Event_Or_Injury[{i}]"] = exposure
        text[S10 + f"ExplainHowDisabilityRelatesToEvent_Exposure_Injury[{i}]"] = explain
        onset = cond.onset_date or ""
        if i == 0:
            text[S10 + "Date_Disability_Began_Or_Worsened[0]"] = onset
        else:
            text[S10 + f"Date12[{i - 1}]"] = onset

    # --- filed a VA claim before? (item 4) ---
    checks[P10 + "RadioButtonList2[0]"] = "0" if p.identity.va_file_number else "1"

    # --- service info (sheet 6 / #subform[11]) ---
    if p.service.periods:
        first = p.service.periods[0]
        m, d, y = _date_parts(first.entry_date)
        text[S11 + "EntryDate_Month[0]"] = m
        text[S11 + "MostRecentActiveServiceEntryDate_Day[0]"] = d
        text[S11 + "EntryDate_Year[0]"] = y
        m, d, y = _date_parts(first.separation_date)
        text[S11 + "ExitDate_Month[0]"], text[S11 + "ExitDate_Day[0]"], \
            text[S11 + "ExitDate_Year[0]"] = m, d, y
        branch_state = next((v for k, v in BRANCH_19A.items()
                             if k in first.branch.lower()), None)
        if branch_state is not None:
            checks[S11 + "RadioButtonList[10]"] = branch_state
        comp_state = next((v for k, v in COMPONENT_19B.items()
                           if k in first.service_component.lower()), None)
        if comp_state is not None:
            checks[S11 + "RadioButtonList[12]"] = comp_state
    checks[S11 + _YESNO_S11["served_other_name"]] = \
        "0" if p.service.served_under_other_name else "1"
    checks[S11 + _YESNO_S11["pow"]] = "0" if p.service.pow else "1"
    if p.service.combat_service:  # only assert YES; leave blank when unknown
        checks[S11 + _YESNO_S11["combat_since_911"]] = "0"
    if p.service.served_under_other_name and p.service.other_name:
        text[S11 + "List_Other_Name_You_Served_Under[0]"] = p.service.other_name

    # --- direct deposit (sheet 7 / #subform[12]) ---
    dd = p.direct_deposit
    text[S12 + "NAME_OF_FINANCIAL_INSTITUTION[0]"] = dd.bank_name
    text[S12 + "Routing_Or_Transit_Number[0]"] = dd.routing_number
    text[S12 + "Account_Number[0]"] = dd.account_number

    return {k: v for k, v in text.items() if v}, checks


F4 = "form1[0].#subform[0]."
F4B = "form1[0].#subform[1]."
_4138_PAGE1_CHARS = 1900


def build_4138(profile: ClaimantProfileData, statement: str) -> tuple[dict, dict]:
    p = profile
    text: dict[str, str] = {}
    text[F4 + "Veterans_Beneficiary_First_Name[0]"] = p.identity.first_name
    text[F4 + "Middle_Initial1[0]"] = p.identity.middle_initial[:1]
    text[F4 + "Last_Name[0]"] = p.identity.last_name
    s1, s2, s3 = _ssn_parts(p.identity.ssn)
    text[F4 + "VETERANSSOCIALSECURITYNUMBERFirstThreeNumbers[0]"] = s1
    text[F4 + "VETERANSSOCIALSECURITYNUMBERSecondTwoNumbers[0]"] = s2
    text[F4 + "VETERANSSOCIALSECURITYNUMBERLastFourNumbers[0]"] = s3
    text[F4B + "VETERANSSOCIALSECURITYNUMBERFirstThreeNumbers[1]"] = s1
    text[F4B + "VETERANSSOCIALSECURITYNUMBERSecondTwoNumbers[1]"] = s2
    text[F4B + "VETERANSSOCIALSECURITYNUMBERLastFourNumbers[1]"] = s3
    text[F4 + "VA_File_Number_If_Applicable[0]"] = p.identity.va_file_number
    text[F4 + "Veterans_Service_Number_If_Applicable[0]"] = p.identity.service_number
    m, d, y = _date_parts(p.identity.date_of_birth)
    text[F4 + "Month[0]"], text[F4 + "Day[0]"], text[F4 + "Year[0]"] = m, d, y
    a, mid, last = _phone_parts(p.contact.phone)
    text[F4 + "AreaCode[0]"], text[F4 + "FirstThreeNumbers[0]"], \
        text[F4 + "LastFourNumbers[0]"] = a, mid, last
    text[F4 + "EMAIL_ADDRESS[0]"] = p.contact.email
    text[F4 + "CurrentMailingAddress_NumberAndStreet[0]"] = p.contact.street
    text[F4 + "CurrentMailingAddress_ApartmentOrUnitNumber[0]"] = p.contact.apt
    text[F4 + "CurrentMailingAddress_City[0]"] = p.contact.city
    text[F4 + "CurrentMailingAddress_StateOrProvince[0]"] = p.contact.state
    text[F4 + "CurrentMailingAddress_Country[0]"] = p.contact.country
    z5, z4 = _zip_parts(p.contact.zip_code)
    text[F4 + "CurrentMailingAddress_ZIPOrPostalCode_FirstFiveNumbers[0]"] = z5
    text[F4 + "CurrentMailingAddress_ZIPOrPostalCode_LastFourNumbers[0]"] = z4

    statement = statement.strip()
    if len(statement) <= _4138_PAGE1_CHARS:
        text[F4 + "REMARKS[0]"] = statement
    else:
        head = textwrap.wrap(statement, _4138_PAGE1_CHARS,
                             break_long_words=False, replace_whitespace=False)[0]
        text[F4 + "REMARKS[0]"] = head + " (CONTINUED ON PAGE 2)"
        text[F4B + "REMARKS[1]"] = statement[len(head):].strip()
    return {k: v for k, v in text.items() if v}, {}


I0 = "form1[0].#subform[0]."


def build_0966(profile: ClaimantProfileData) -> tuple[dict, dict]:
    p = profile
    text: dict[str, str] = {}
    text[I0 + "VeteransFirstName[0]"] = p.identity.first_name
    text[I0 + "VeteransMiddleInitial1[0]"] = p.identity.middle_initial[:1]
    text[I0 + "VeteransLastName[0]"] = p.identity.last_name
    s1, s2, s3 = _ssn_parts(p.identity.ssn)
    text[I0 + "FirstThreeNumbers[0]"] = s1
    text[I0 + "SecondTwoNumbers[0]"] = s2
    text[I0 + "LastFourNumbers[0]"] = s3
    text[I0 + "VAFileNumber[0]"] = p.identity.va_file_number
    m, d, y = _date_parts(p.identity.date_of_birth)
    text[I0 + "Month[0]"], text[I0 + "Day[0]"], text[I0 + "Year[0]"] = m, d, y
    text[I0 + "VeteransServiceNumber[0]"] = p.identity.service_number
    text[I0 + "CurrentMailingAddress_NumberAndStreet[0]"] = p.contact.street
    text[I0 + "CurrentMailingAddress_ApartmentOrUnitNumber[0]"] = p.contact.apt
    text[I0 + "CurrentMailingAddress_City[0]"] = p.contact.city
    text[I0 + "CurrentMailingAddress_StateOrProvince[0]"] = p.contact.state
    text[I0 + "CurrentMailingAddress_Country[0]"] = p.contact.country
    z5, z4 = _zip_parts(p.contact.zip_code)
    text[I0 + "CurrentMailingAddress_ZIPOrPostalCode_FirstFiveNumbers[0]"] = z5
    text[I0 + "CurrentMailingAddress_ZIPOrPostalCode_LastFourNumbers[0]"] = z4
    a, mid, last = _phone_parts(p.contact.phone)
    text[I0 + "AreaCode[0]"] = a
    text[I0 + "FirstThreeNumbers[1]"] = mid
    text[I0 + "LastFourNumbers[1]"] = last
    text[I0 + "EmailAddress1[0]"] = p.contact.email
    checks = {
        # ITF is for disability compensation (page-2 benefit checkboxes)
        "form1[0].#subform[1].Compensation[0]": "1",
        # previously filed a claim? (/0 YES, /1 NO)
        I0 + "RadioButtonList[0]": "0" if p.identity.va_file_number else "1",
    }
    return {k: v for k, v in text.items() if v}, checks
