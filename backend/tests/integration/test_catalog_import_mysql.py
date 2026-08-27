import os
from decimal import Decimal
from importlib import import_module
from io import BytesIO
from pathlib import Path

import pytest
from dotenv import load_dotenv
from openpyxl import Workbook
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.catalog.service import create_product, is_pack_code_ambiguous
from app.db.schema import initialize_database
from app.models.catalog import CigaretteProduct

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
HEADERS = ["条码", "品规名称", "包码", "品牌", "零售价格", "包数量", "条数量"]


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def catalog_excel():
    try:
        return import_module("app.catalog.excel")
    except ModuleNotFoundError:
        pytest.fail("app.catalog.excel 尚未实现")


def workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def reset_products() -> None:
    initialize_database(database_url_for_test())
    engine = create_engine(database_url_for_test())
    with Session(engine) as session, session.begin():
        session.execute(delete(CigaretteProduct))
    engine.dispose()


def test_import_creates_updates_warns_and_keeps_duplicate_pack_codes() -> None:
    reset_products()
    excel = catalog_excel()
    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        create_product(
            session,
            carton_code="6901028000103",
            pack_code=None,
            brand="已有品牌",
            standard_name="已有版本",
            carton_retail_price=Decimal("90.00"),
            sticks_per_pack=20,
            packs_per_carton=10,
        )
        content = workbook_bytes(
            [
                ["6901028000103", "已有版本（更新）", -1, "已有品牌", 100, 20, 200],
                ["6901028000110", "新增版本一", "6901028000103", "测试品牌", 120, 20, 200],
                ["6901028000127", "新增版本二", "6901028000134", "测试品牌", 130, 20, 200],
                ["6901028000141", "新增版本三", "6901028000134", "测试品牌", 140, 20, 200],
            ]
        )

        result = excel.import_products_from_workbook(session, content)

        assert result.total_rows == 4
        assert result.created_count == 3
        assert result.updated_count == 1
        assert result.skipped_count == 0
        assert result.warning_count == 1
        assert [(issue.row_number, issue.code) for issue in result.issues] == [
            (3, "PACK_CODE_CONFLICT_CLEARED")
        ]
        updated = session.scalar(
            select(CigaretteProduct).where(
                CigaretteProduct.carton_code == "6901028000103"
            )
        )
        cleared = session.scalar(
            select(CigaretteProduct).where(
                CigaretteProduct.carton_code == "6901028000110"
            )
        )
        assert updated is not None
        assert updated.standard_name == "已有版本（更新）"
        assert updated.carton_retail_price == Decimal("100.00")
        assert cleared is not None
        assert cleared.pack_code is None
        assert is_pack_code_ambiguous(session, "6901028000134") is True
    engine.dispose()
