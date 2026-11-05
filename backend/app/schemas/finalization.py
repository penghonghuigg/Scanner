from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.scanning import (
    ProductSnapshotResponse,
    ScanEventResponse,
    ScanSessionItemResponse,
    ScanSessionResponse,
    ScanSummaryResponse,
)

SourceType = Literal[
    "OUTSIDE_PROVINCE",
    "UNKNOWN",
    "LOCAL_HUAINAN",
    "ANHUI_OTHER_CITY",
]


class SourceTypeOption(BaseModel):
    value: SourceType
    label: str


class RegionCity(BaseModel):
    name: str


class RegionProvince(BaseModel):
    name: str
    cities: list[RegionCity]


class RegionCatalogPayload(BaseModel):
    source_types: list[SourceTypeOption]
    provinces: list[RegionProvince]


class SourceAllocationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: SourceType
    province_name: str | None = Field(default=None, max_length=50)
    city_name: str | None = Field(default=None, max_length=80)
    pack_count: int = Field(gt=0)


class SourceAllocationReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[SourceAllocationInput] = Field(min_length=1)


class ResultItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    product_id: int = Field(gt=0)
    quantity_cartons: Decimal = Field(
        ge=Decimal("0.1"),
        multiple_of=Decimal("0.1"),
    )
    source_allocations: list[SourceAllocationInput] = Field(min_length=1)


class ResultItemReplaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    quantity_cartons: Decimal = Field(
        ge=Decimal("0.1"),
        multiple_of=Decimal("0.1"),
    )
    source_allocations: list[SourceAllocationInput] = Field(min_length=1)


class SourceAllocationResponse(BaseModel):
    id: int
    source_type: SourceType
    source_type_name: str
    province_name: str | None
    city_name: str | None
    pack_count: int
    equivalent_cartons: str
    quantity_sticks: int


class ProductSourceAllocationState(BaseModel):
    product_id: int
    product_snapshot: ProductSnapshotResponse
    required_pack_count: int
    allocated_pack_count: int
    remaining_pack_count: int
    allocations: list[SourceAllocationResponse]


class ResultItemOperationPayload(BaseModel):
    item: ScanSessionItemResponse
    source_state: ProductSourceAllocationState
    event: ScanEventResponse
    idempotent_replay: bool


class SourceAllocationListPayload(BaseModel):
    items: list[ProductSourceAllocationState]


class CompleteScanSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_exceptions: bool = False


class CompletionSummaryResponse(BaseModel):
    scan_session: ScanSessionResponse
    summary: ScanSummaryResponse
    source_product_count: int
    source_allocated_product_count: int
    unknown_count: int
    unresolved_ambiguity_count: int


class ExportRecordResponse(BaseModel):
    id: int
    session_id: int
    filename: str
    file_size: int
    file_sha256: str
    template_version: str
    generated_by: int
    created_at: datetime
