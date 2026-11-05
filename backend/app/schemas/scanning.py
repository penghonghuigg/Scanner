from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateScanSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_type: str = Field(min_length=1, max_length=32)
    filing_case_no: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)
    branch_code: str | None = Field(default=None, max_length=20)


class ScanSessionResponse(BaseModel):
    id: int
    session_no: str
    business_type: str
    business_type_name: str
    filing_case_no: str | None
    location: str | None
    notes: str | None
    branch_code: str
    branch_name: str
    operator_id: int
    operator_name: str
    status: str
    status_name: str
    completed_at: datetime | None
    product_count: int
    total_sticks: int
    display_label: str
    created_at: datetime
    updated_at: datetime


class ScanSessionPayload(BaseModel):
    scan_session: ScanSessionResponse


class ScanSessionListPayload(BaseModel):
    items: list[ScanSessionResponse]
    total: int
    page: int
    page_size: int


class ScanCodeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    code: str = Field(min_length=6, max_length=64, pattern=r"^\d{6,64}$")


class ResolveAmbiguityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    event_id: int = Field(gt=0)
    product_id: int = Field(gt=0)


class AdjustCartonQuantityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    operation: Literal["DELTA", "SET"]
    quantity: Decimal = Field(multiple_of=Decimal("0.1"))
    reason_type: Literal[
        "ONSITE_VERIFICATION",
        "SCAN_CORRECTION",
        "LOOSE_PACK_VERIFICATION",
        "OTHER",
    ]
    reason_note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_other_reason_note(self) -> "AdjustCartonQuantityRequest":
        if self.reason_type == "OTHER" and not (self.reason_note or "").strip():
            raise ValueError("选择其他时必须填写具体调整原因")
        return self


class RemoveScanSessionItemRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID


class ProductSnapshotResponse(BaseModel):
    product_id: int
    carton_code: str
    pack_code: str | None
    brand: str
    standard_name: str
    carton_retail_price: str | None
    sticks_per_pack: int
    packs_per_carton: int
    sticks_per_carton: int


class ScanSessionItemResponse(BaseModel):
    id: int
    product_id: int
    carton_count: int
    pack_count: int
    manual_delta_sticks: int
    total_sticks: int
    product_snapshot: ProductSnapshotResponse
    updated_at: datetime


class ScanEventResponse(BaseModel):
    id: int
    request_id: UUID
    event_type: str
    result: str
    raw_code: str
    product_id: int | None
    unit_type: str | None
    delta_sticks: int
    reason: str | None
    source_event_id: int | None
    candidate_snapshot: list[ProductSnapshotResponse] | None
    product_snapshot: ProductSnapshotResponse | None
    operator_id: int
    operator_name: str
    resolved: bool
    created_at: datetime


class ScanSummaryResponse(BaseModel):
    product_count: int
    carton_count: int
    pack_count: int
    total_sticks: int
    unknown_count: int
    ambiguous_count: int


class CatalogSummaryResponse(BaseModel):
    active_code_count: int
    active_standard_product_count: int


class ScanStateResponse(BaseModel):
    summary: ScanSummaryResponse
    items: list[ScanSessionItemResponse]
    recent_events: list[ScanEventResponse]
    pending_ambiguities: list[ScanEventResponse]
    catalog_summary: CatalogSummaryResponse
    latest_successful_event: ScanEventResponse | None


class ScanEventListPayload(BaseModel):
    items: list[ScanEventResponse]
    total: int
    page: int
    page_size: int


class ScanOperationResponse(BaseModel):
    event: ScanEventResponse
    state: ScanStateResponse
    idempotent_replay: bool
