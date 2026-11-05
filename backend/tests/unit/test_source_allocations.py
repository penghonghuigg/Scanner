from decimal import Decimal

import pytest

from app.scanning.regions import SourceLocationInvalidError
from app.scanning.source_service import (
    QuantityNotPackAlignedError,
    SourceQuantityMismatchError,
    normalize_allocations,
    required_pack_count,
)


def allocation(
    source_type: str,
    province_name: str | None,
    city_name: str | None,
    pack_count: int,
) -> dict[str, object]:
    return {
        "source_type": source_type,
        "province_name": province_name,
        "city_name": city_name,
        "pack_count": pack_count,
    }


def test_normalize_allocations_merges_same_source_and_converts_units() -> None:
    result = normalize_allocations(
        [
            allocation("OUTSIDE_PROVINCE", "天津市", "天津市", 2),
            allocation("OUTSIDE_PROVINCE", "天津市", "天津市", 3),
        ],
        sticks_per_pack=20,
        required_sticks=100,
    )

    assert len(result) == 1
    assert result[0].source_type == "OUTSIDE_PROVINCE"
    assert result[0].province_name == "天津市"
    assert result[0].city_name == "天津市"
    assert result[0].pack_count == 5
    assert result[0].quantity_sticks == 100
    assert result[0].equivalent_cartons == Decimal("0.5")
    assert result[0].source_key == "OUTSIDE_PROVINCE|天津市|天津市"


def test_normalize_allocations_merges_unknown_cities_in_the_same_province() -> None:
    result = normalize_allocations(
        [
            allocation("OUTSIDE_PROVINCE", "天津市", None, 2),
            allocation("OUTSIDE_PROVINCE", "天津市", "不详", 3),
        ],
        sticks_per_pack=20,
        required_sticks=100,
    )

    assert len(result) == 1
    assert result[0].city_name == "不详"
    assert result[0].pack_count == 5
    assert result[0].source_key == "OUTSIDE_PROVINCE|天津市|不详"


def test_normalize_allocations_keeps_different_sources_as_flat_rows() -> None:
    result = normalize_allocations(
        [
            allocation("OUTSIDE_PROVINCE", "天津市", "天津市", 15),
            allocation("UNKNOWN", None, None, 3),
        ],
        sticks_per_pack=20,
        required_sticks=360,
    )

    assert [item.pack_count for item in result] == [15, 3]
    assert [item.quantity_sticks for item in result] == [300, 60]


@pytest.mark.parametrize("pack_count", [0, -1, 1.5, "2"])
def test_normalize_allocations_rejects_non_positive_or_non_integer_pack_count(
    pack_count: object,
) -> None:
    with pytest.raises(SourceQuantityMismatchError):
        normalize_allocations(
            [allocation("UNKNOWN", None, None, pack_count)],  # type: ignore[arg-type]
            sticks_per_pack=20,
            required_sticks=20,
        )


def test_normalize_allocations_rejects_invalid_location() -> None:
    with pytest.raises(SourceLocationInvalidError):
        normalize_allocations(
            [allocation("OUTSIDE_PROVINCE", "安徽省", "合肥市", 1)],
            sticks_per_pack=20,
            required_sticks=20,
        )


def test_normalize_allocations_requires_exact_final_quantity() -> None:
    with pytest.raises(SourceQuantityMismatchError):
        normalize_allocations(
            [allocation("UNKNOWN", None, None, 4)],
            sticks_per_pack=20,
            required_sticks=100,
        )


def test_required_pack_count_rejects_non_pack_aligned_total() -> None:
    assert required_pack_count(total_sticks=360, sticks_per_pack=20) == 18
    with pytest.raises(QuantityNotPackAlignedError):
        required_pack_count(total_sticks=361, sticks_per_pack=20)
