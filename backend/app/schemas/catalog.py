from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carton_code: str = Field(min_length=6, max_length=64)
    pack_code: str | None = Field(default=None, min_length=6, max_length=64)
    brand: str = Field(min_length=1, max_length=100)
    standard_name: str = Field(min_length=1, max_length=200)
    carton_retail_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    sticks_per_pack: int = Field(gt=0, le=65535)
    packs_per_carton: int = Field(gt=0, le=65535)
    is_active: bool = True


class UpdateProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    carton_code: str | None = Field(default=None, min_length=6, max_length=64)
    pack_code: str | None = Field(default=None, min_length=6, max_length=64)
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    standard_name: str | None = Field(default=None, min_length=1, max_length=200)
    carton_retail_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    sticks_per_pack: int | None = Field(default=None, gt=0, le=65535)
    packs_per_carton: int | None = Field(default=None, gt=0, le=65535)
    is_active: bool | None = None

    @model_validator(mode="after")
    def reject_null_for_required_columns(self) -> "UpdateProductRequest":
        nullable_fields = {"pack_code", "carton_retail_price"}
        invalid_fields = {
            field
            for field in self.model_fields_set - nullable_fields
            if getattr(self, field) is None
        }
        if invalid_fields:
            raise ValueError(f"以下字段不能设置为空：{', '.join(sorted(invalid_fields))}")
        return self


class ProductResponse(BaseModel):
    id: int
    carton_code: str
    pack_code: str | None
    brand: str
    standard_name: str
    carton_retail_price: Decimal | None
    pack_retail_price: Decimal | None
    sticks_per_pack: int
    packs_per_carton: int
    sticks_per_carton: int
    is_pack_ambiguous: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductPayload(BaseModel):
    product: ProductResponse


class ProductSummary(BaseModel):
    total_count: int
    active_count: int
    inactive_count: int
    ambiguous_count: int


class ProductListPayload(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    summary: ProductSummary


class ImportIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row_number: int
    level: str
    field: str
    code: str
    message: str
    carton_code: str
    standard_name: str


class ProductImportPayload(BaseModel):
    total_rows: int
    created_count: int
    updated_count: int
    skipped_count: int
    warning_count: int
    issues: list[ImportIssueResponse]
