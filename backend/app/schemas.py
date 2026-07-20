from __future__ import annotations

from pydantic import BaseModel, Field


class VeteranIdentity(BaseModel):
    first_name: str = ""
    middle_initial: str = ""
    last_name: str = ""
    ssn: str = ""  # stays on-device; rendered into the PDF only
    va_file_number: str = ""
    date_of_birth: str = ""  # YYYY-MM-DD
    service_number: str = ""


class ContactInfo(BaseModel):
    phone: str = ""
    email: str = ""
    street: str = ""
    apt: str = ""
    city: str = ""
    state: str = ""
    country: str = "US"  # 2-char field on the VA forms
    zip_code: str = ""


class ServicePeriod(BaseModel):
    branch: str = ""
    entry_date: str = ""  # YYYY-MM-DD
    separation_date: str = ""
    service_component: str = "Active"  # Active|Reserves|National Guard
    character_of_discharge: str = ""


class ServiceInfo(BaseModel):
    periods: list[ServicePeriod] = Field(default_factory=list)
    served_under_other_name: bool = False
    other_name: str = ""
    pow: bool = False
    combat_service: bool = False
    exposures: list[str] = Field(default_factory=list)  # burn pits, agent orange, ...


class DirectDeposit(BaseModel):
    """Optional; the veteran can leave blank and give the VA this separately."""

    account_type: str = ""  # Checking|Savings
    bank_name: str = ""
    routing_number: str = ""
    account_number: str = ""


class ClaimantProfileData(BaseModel):
    claim_process: str = "FDC"  # FDC|Standard
    itf_date: str = ""  # date an Intent to File was submitted (YYYY-MM-DD)
    identity: VeteranIdentity = Field(default_factory=VeteranIdentity)
    contact: ContactInfo = Field(default_factory=ContactInfo)
    service: ServiceInfo = Field(default_factory=ServiceInfo)
    direct_deposit: DirectDeposit = Field(default_factory=DirectDeposit)


class ConditionIn(BaseModel):
    name: str
    basis: str = "direct"
    secondary_to: str | None = None
    onset_date: str | None = None
    exposure: str | None = None
    notes: str = ""
    status: str = "selected"
    sort: int = 0


class ConditionOut(ConditionIn):
    id: int
    case_id: int

    model_config = {"from_attributes": True}


# ---- LLM structured-output schemas ----

class PrefillCondition(BaseModel):
    name: str
    basis: str = "direct"
    onset_date: str | None = None
    evidence_note: str = ""


class IdentityPrefill(BaseModel):
    """Identity/service extraction target. Small on purpose: local models are
    far more reliable with narrow schemas."""

    identity: VeteranIdentity = Field(default_factory=VeteranIdentity)
    service: ServiceInfo = Field(default_factory=ServiceInfo)


class ConditionsPrefill(BaseModel):
    candidate_conditions: list[PrefillCondition] = Field(default_factory=list)


class ProfilePrefill(BaseModel):
    """Merged result of both prefill passes. Everything is a draft the veteran
    reviews; missing = empty string."""

    identity: VeteranIdentity = Field(default_factory=VeteranIdentity)
    service: ServiceInfo = Field(default_factory=ServiceInfo)
    candidate_conditions: list[PrefillCondition] = Field(default_factory=list)
