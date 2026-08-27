import os
from decimal import Decimal
from importlib import import_module
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.db.schema import initialize_database
from app.models.catalog import CigaretteProduct

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def catalog_service():
    try:
        return import_module("app.catalog.service")
    except ModuleNotFoundError:
        pytest.fail("app.catalog.service 尚未实现")


def reset_products() -> None:
    database_url = database_url_for_test()
    initialize_database(database_url)
    engine = create_engine(database_url)
    with Session(engine) as session, session.begin():
        session.execute(delete(CigaretteProduct))
    engine.dispose()


def product_values(**overrides):
    values = {
        "carton_code": "6901028000011",
        "pack_code": "6901028000028",
        "brand": "测试品牌",
        "standard_name": "测试品牌（经典）",
        "carton_retail_price": Decimal("100.00"),
        "sticks_per_pack": 20,
        "packs_per_carton": 10,
        "is_active": True,
    }
    values.update(overrides)
    return values


def test_same_name_with_different_carton_codes_creates_distinct_versions() -> None:
    reset_products()
    service = catalog_service()
    engine = create_engine(database_url_for_test())

    with Session(engine) as session:
        first = service.create_product(session, **product_values())
        second = service.create_product(
            session,
            **product_values(
                carton_code="6901028000035",
                pack_code="6901028000042",
                carton_retail_price=Decimal("120.00"),
            ),
        )

        assert first.id != second.id
        assert first.standard_name == second.standard_name
        assert first.carton_retail_price == Decimal("100.00")
        assert second.carton_retail_price == Decimal("120.00")
    engine.dispose()


def test_duplicate_carton_code_is_rejected() -> None:
    reset_products()
    service = catalog_service()
    engine = create_engine(database_url_for_test())

    with Session(engine) as session:
        service.create_product(session, **product_values())
        with pytest.raises(service.CartonCodeExistsError):
            service.create_product(
                session,
                **product_values(pack_code="6901028000097"),
            )
    engine.dispose()


def test_duplicate_pack_code_is_allowed_and_marked_ambiguous() -> None:
    reset_products()
    service = catalog_service()
    engine = create_engine(database_url_for_test())

    with Session(engine) as session:
        first = service.create_product(session, **product_values())
        second = service.create_product(
            session,
            **product_values(carton_code="6901028000035"),
        )

        assert service.is_pack_code_ambiguous(session, first.pack_code) is True
        assert service.is_pack_code_ambiguous(session, second.pack_code) is True
    engine.dispose()


def test_pack_and_carton_cross_type_conflicts_are_rejected() -> None:
    reset_products()
    service = catalog_service()
    engine = create_engine(database_url_for_test())

    with Session(engine) as session:
        service.create_product(session, **product_values())
        with pytest.raises(service.PackCodeConflictError):
            service.create_product(
                session,
                **product_values(
                    carton_code="6901028000035",
                    pack_code="6901028000011",
                ),
            )
        with pytest.raises(service.PackCodeConflictError):
            service.create_product(
                session,
                **product_values(
                    carton_code="6901028000028",
                    pack_code="6901028000042",
                ),
            )
    engine.dispose()
