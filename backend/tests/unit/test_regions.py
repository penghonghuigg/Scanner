import pytest

from app.scanning.regions import (
    SourceLocationInvalidError,
    region_catalog,
    source_key,
    validate_source_location,
)


def region_pairs() -> list[tuple[str, str]]:
    return [
        (province["name"], city)
        for province in region_catalog()
        for city in province["cities"]
    ]


def test_region_catalog_excludes_special_regions_invalid_placeholders_and_duplicates() -> None:
    pairs = region_pairs()

    assert ("香港特别行政区", "香港特别行政区") not in pairs
    assert ("澳门特别行政区", "澳门特别行政区") not in pairs
    assert ("山西省", "山西省") not in pairs
    assert ("福建省", "福建省") not in pairs
    assert ("台湾省", "台湾省") in pairs
    assert pairs.count(("湖北省", "恩施土家族苗族自治州")) == 1
    assert pairs.count(("海南省", "儋州市")) == 1


@pytest.mark.parametrize("municipality", ["北京市", "天津市", "上海市", "重庆市"])
def test_municipalities_use_the_same_province_and_city_name(municipality: str) -> None:
    assert (municipality, municipality) in region_pairs()


def test_validate_source_location_enforces_the_four_source_rules() -> None:
    assert validate_source_location("UNKNOWN", None, None) == (None, None)
    assert validate_source_location("LOCAL_HUAINAN", None, None) == (
        "安徽省",
        "淮南市",
    )
    assert validate_source_location("ANHUI_OTHER_CITY", None, "合肥市") == (
        "安徽省",
        "合肥市",
    )
    assert validate_source_location("OUTSIDE_PROVINCE", "天津市", "天津市") == (
        "天津市",
        "天津市",
    )


def test_outside_province_allows_unknown_city() -> None:
    assert validate_source_location("OUTSIDE_PROVINCE", "天津市", None) == (
        "天津市",
        "不详",
    )
    assert validate_source_location("OUTSIDE_PROVINCE", "福建省", "") == (
        "福建省",
        "不详",
    )


@pytest.mark.parametrize(
    ("source_type", "province", "city"),
    [
        ("UNKNOWN", "安徽省", "淮南市"),
        ("OUTSIDE_PROVINCE", "安徽省", "合肥市"),
        ("OUTSIDE_PROVINCE", "福建省", "不存在市"),
        ("ANHUI_OTHER_CITY", "安徽省", "淮南市"),
        ("ANHUI_OTHER_CITY", "安徽省", "不存在市"),
        ("INVALID", None, None),
    ],
)
def test_validate_source_location_rejects_invalid_combinations(
    source_type: str,
    province: str | None,
    city: str | None,
) -> None:
    with pytest.raises(SourceLocationInvalidError):
        validate_source_location(source_type, province, city)


def test_source_key_uses_normalized_location() -> None:
    assert source_key("LOCAL_HUAINAN", None, None) == (
        "LOCAL_HUAINAN|安徽省|淮南市"
    )
    assert source_key("UNKNOWN", None, None) == "UNKNOWN||"
    assert source_key("OUTSIDE_PROVINCE", "天津市", None) == (
        "OUTSIDE_PROVINCE|天津市|不详"
    )
