import asyncio
import os
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openpyxl import Workbook, load_workbook
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.models.auth import User, UserSession
from app.models.catalog import CigaretteProduct
from app.models.finalization import ExportRecord, ScanItemSourceAllocation
from app.models.integration import IntegrationSnapshot
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
HEADERS = ["条码", "品规名称", "包码", "品牌", "零售价格", "包数量", "条数量"]


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def prepare_catalog_users() -> None:
    database_url = database_url_for_test()
    initialize_database(database_url)
    engine = create_engine(database_url)
    now = datetime.now(UTC).replace(tzinfo=None)
    with Session(engine) as session, session.begin():
        session.execute(delete(ExportRecord))
        session.execute(delete(ScanItemSourceAllocation))
        session.execute(delete(ScanEvent).where(ScanEvent.source_event_id.is_not(None)))
        session.execute(delete(ScanEvent))
        session.execute(delete(ScanSessionItem))
        session.execute(delete(UserSession))
        session.execute(delete(IntegrationSnapshot))
        session.execute(delete(ScanSession))
        session.execute(delete(CigaretteProduct))
        session.execute(delete(User))
        session.add_all(
            [
                User(
                    username="admin",
                    password_hash=hash_password("admin-password"),
                    display_name="系统管理员",
                    role="ADMIN",
                    branch_code=None,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
                User(
                    username="operator",
                    password_hash=hash_password("operator-password"),
                    display_name="普通人员",
                    role="OPERATOR",
                    branch_code="FENGTAI",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
    engine.dispose()


def make_app():
    from app.main import create_app

    return create_app(
        Settings(
            app_env="test",
            database_url=database_url_for_test(),
            cookie_secure=False,
            allowed_origins="http://testserver",
        )
    )


async def login(client: httpx.AsyncClient, username: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200


def product_payload(**overrides):
    payload = {
        "carton_code": "6901028000011",
        "pack_code": "6901028000028",
        "brand": "测试品牌",
        "standard_name": "测试品牌（经典）",
        "carton_retail_price": "100.00",
        "sticks_per_pack": 20,
        "packs_per_carton": 10,
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def workbook_bytes() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    sheet.append(["6901028000035", "导入版本", -1, "导入品牌", 120, 20, 200])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_admin_creates_queries_updates_and_downloads_the_template() -> None:
    prepare_catalog_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            await login(client, "admin", "admin-password")
            created = await client.post(
                "/api/v1/products",
                json=product_payload(),
                headers={"Origin": "http://testserver"},
            )
            assert created.status_code == 201
            product = created.json()["data"]["product"]
            assert set(product) == {
                "id",
                "carton_code",
                "pack_code",
                "brand",
                "standard_name",
                "carton_retail_price",
                "pack_retail_price",
                "sticks_per_pack",
                "packs_per_carton",
                "sticks_per_carton",
                "is_pack_ambiguous",
                "is_active",
                "created_at",
                "updated_at",
            }
            assert product["carton_retail_price"] == "100.00"
            assert product["pack_retail_price"] == "10.00"
            assert product["sticks_per_carton"] == 200

            listing = await client.get("/api/v1/products", params={"query": "经典"})
            assert listing.status_code == 200
            assert listing.json()["data"]["total"] == 1
            assert listing.json()["data"]["items"][0]["id"] == product["id"]

            updated = await client.patch(
                f"/api/v1/products/{product['id']}",
                json={"carton_retail_price": "120.00", "is_active": False},
                headers={"Origin": "http://testserver"},
            )
            assert updated.status_code == 200
            assert updated.json()["data"]["product"]["pack_retail_price"] == "12.00"
            assert updated.json()["data"]["product"]["is_active"] is False

            template = await client.get("/api/v1/products/import-template.xlsx")
            assert template.status_code == 200
            assert template.headers["content-type"].startswith(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            assert load_workbook(BytesIO(template.content)).sheetnames == [
                "品规导入",
                "填写说明",
            ]

    asyncio.run(scenario())


def test_admin_imports_an_xlsx_and_receives_counts() -> None:
    prepare_catalog_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            await login(client, "admin", "admin-password")
            response = await client.post(
                "/api/v1/products/import",
                files={
                    "file": (
                        "products.xlsx",
                        workbook_bytes(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
                headers={"Origin": "http://testserver"},
            )
            assert response.status_code == 200
            assert response.json()["data"] == {
                "total_rows": 1,
                "created_count": 1,
                "updated_count": 0,
                "skipped_count": 0,
                "warning_count": 0,
                "issues": [],
            }

    asyncio.run(scenario())


def test_catalog_endpoints_require_admin_and_writes_require_origin() -> None:
    prepare_catalog_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            anonymous = await client.get("/api/v1/products")
            assert anonymous.status_code == 401

            await login(client, "operator", "operator-password")
            forbidden = await client.get("/api/v1/products")
            assert forbidden.status_code == 403
            assert forbidden.json()["error"]["code"] == "FORBIDDEN"

            await login(client, "admin", "admin-password")
            bad_origin = await client.post("/api/v1/products", json=product_payload())
            assert bad_origin.status_code == 403
            assert bad_origin.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"

    asyncio.run(scenario())
