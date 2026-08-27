from decimal import Decimal
from importlib import import_module

import pytest


def catalog_service():
    try:
        return import_module("app.catalog.service")
    except ModuleNotFoundError:
        pytest.fail("app.catalog.service 尚未实现")


def test_pack_price_uses_decimal_and_rounds_half_up() -> None:
    service = catalog_service()

    assert service.calculate_pack_price(Decimal("100.00"), 3) == Decimal("33.33")
    assert service.calculate_pack_price(Decimal("100.01"), 2) == Decimal("50.01")
    assert service.calculate_pack_price(None, 10) is None


def test_product_totals_are_derived_from_authoritative_fields() -> None:
    service = catalog_service()

    assert service.calculate_sticks_per_carton(20, 10) == 200
