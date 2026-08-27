import pytest
from sqlalchemy.dialects import mysql

from app.db.base import Base


def catalog_table():
    try:
        from app.models import catalog  # noqa: F401
    except ImportError:
        pytest.fail("app.models.catalog 尚未实现")
    return Base.metadata.tables["cigarette_products"]


def test_catalog_metadata_matches_the_single_table_contract() -> None:
    products = catalog_table()

    assert set(products.c.keys()) == {
        "id",
        "carton_code",
        "pack_code",
        "brand",
        "standard_name",
        "carton_retail_price",
        "sticks_per_pack",
        "packs_per_carton",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert products.c.id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert products.c.carton_code.unique is True
    assert products.c.carton_code.type.length == 64
    assert products.c.pack_code.unique is not True
    assert products.c.pack_code.nullable is True
    assert products.c.carton_retail_price.type.precision == 12
    assert products.c.carton_retail_price.type.scale == 2
    assert products.c.carton_retail_price.default is None
    assert products.c.carton_retail_price.nullable is True
    assert products.c.sticks_per_pack.type.dialect_impl(mysql.dialect()).unsigned is True
    assert products.c.packs_per_carton.type.dialect_impl(mysql.dialect()).unsigned is True
    assert products.c.is_active.server_default.arg.text == "1"
    assert {index.name for index in products.indexes} == {
        "idx_products_pack_active",
        "idx_products_name",
    }
def test_catalog_table_uses_mysql_persistent_options() -> None:
    products = catalog_table()

    assert products.dialect_options["mysql"]["engine"] == "InnoDB"
    assert products.dialect_options["mysql"]["charset"] == "utf8mb4"
    assert products.dialect_options["mysql"]["collate"] == "utf8mb4_0900_ai_ci"
