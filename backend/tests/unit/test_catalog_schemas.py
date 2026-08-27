import pytest
from pydantic import ValidationError

from app.schemas.catalog import UpdateProductRequest


@pytest.mark.parametrize(
    "field",
    (
        "carton_code",
        "brand",
        "standard_name",
        "sticks_per_pack",
        "packs_per_carton",
        "is_active",
    ),
)
def test_non_nullable_patch_fields_reject_explicit_null(field: str) -> None:
    with pytest.raises(ValidationError):
        UpdateProductRequest.model_validate({field: None})


def test_nullable_patch_fields_accept_explicit_null() -> None:
    payload = UpdateProductRequest.model_validate(
        {"pack_code": None, "carton_retail_price": None}
    )

    assert payload.model_dump(exclude_unset=True) == {
        "pack_code": None,
        "carton_retail_price": None,
    }
