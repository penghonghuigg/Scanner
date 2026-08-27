from datetime import datetime

import pytest


def scanning_service():
    try:
        from app.scanning import service
    except ModuleNotFoundError:
        pytest.fail("app.scanning.service 尚未实现")
    return service


def test_session_number_uses_china_time_and_fixed_suffix() -> None:
    service = scanning_service()

    assert service.generate_session_no(
        now=datetime(2026, 8, 27, 8, 30, 45),
        suffix=4821,
    ) == "PD20260827-163045-4821"


def test_business_type_and_status_have_chinese_names() -> None:
    service = scanning_service()

    assert service.business_type_name("MARKET_INSPECTION") == "市场检查"
    assert service.business_type_name("DELIVERY_CHANNEL") == "寄递渠道"
    assert service.business_type_name("SPECIAL_TRANSPORT") == "专车运输"
    assert service.business_type_name("OTHER") == "其他"
    assert service.status_name("DRAFT") == "进行中"


def test_display_label_places_date_before_operator_and_zero_counts() -> None:
    service = scanning_service()

    assert service.build_display_label(
        created_at=datetime(2026, 8, 27, 8, 30),
        operator_name="张三",
        product_count=0,
        total_sticks=0,
    ) == "2026-08-27 16:30—张三—0个品规—0支卷烟"
