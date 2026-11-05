import asyncio
import os
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openpyxl import load_workbook
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


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


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


def prepare_product_options() -> dict[str, int]:
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
        operator = User(
                username="result-operator",
                password_hash=hash_password("operator-password"),
                display_name="凤台操作员",
                role="OPERATOR",
                branch_code="FENGTAI",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        coworker = User(
            username="result-coworker",
            password_hash=hash_password("coworker-password"),
            display_name="凤台协作人员",
            role="OPERATOR",
            branch_code="FENGTAI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        viewer = User(
            username="result-viewer",
            password_hash=hash_password("viewer-password"),
            display_name="凤台查看员",
            role="VIEWER",
            branch_code="FENGTAI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        other = User(
            username="result-other",
            password_hash=hash_password("other-password"),
            display_name="潘集操作员",
            role="OPERATOR",
            branch_code="PANJI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        admin = User(
            username="result-admin",
            password_hash=hash_password("admin-password"),
            display_name="系统管理员",
            role="ADMIN",
            branch_code=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        active_product = CigaretteProduct(
                    carton_code="6901028129756",
                    pack_code=None,
                    brand="黄山",
                    standard_name="黄山(红方印金中支)",
                    carton_retail_price=Decimal("400.00"),
                    sticks_per_pack=20,
                    packs_per_carton=10,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
        inactive_product = CigaretteProduct(
                    carton_code="6901028045919",
                    pack_code=None,
                    brand="云烟",
                    standard_name="云烟(软珍品)",
                    carton_retail_price=Decimal("230.00"),
                    sticks_per_pack=20,
                    packs_per_carton=10,
                    is_active=False,
                    created_at=now,
                    updated_at=now,
                )
        session.add_all(
            [operator, coworker, viewer, other, admin, active_product, inactive_product]
        )
        session.flush()
        completed = ScanSession(
            session_no="PD20260902-180000-0001",
            business_type="MARKET_INSPECTION",
            filing_case_no=None,
            location=None,
            notes=None,
            branch_code="FENGTAI",
            operator_id=operator.id,
            status="COMPLETED",
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        draft = ScanSession(
            session_no="PD20260902-180000-0002",
            business_type="MARKET_INSPECTION",
            filing_case_no=None,
            location=None,
            notes=None,
            branch_code="FENGTAI",
            operator_id=operator.id,
            status="DRAFT",
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        other_completed = ScanSession(
            session_no="PD20260902-180000-0003",
            business_type="MARKET_INSPECTION",
            filing_case_no=None,
            location=None,
            notes=None,
            branch_code="PANJI",
            operator_id=other.id,
            status="COMPLETED",
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        admin_completed = ScanSession(
            session_no="PD20260902-180000-0004",
            business_type="OTHER",
            filing_case_no=None,
            location=None,
            notes=None,
            branch_code="FENGTAI",
            operator_id=admin.id,
            status="COMPLETED",
            completed_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add_all([completed, draft, other_completed, admin_completed])
        session.flush()
        result = {
            "active_product": active_product.id,
            "inactive_product": inactive_product.id,
            "completed": completed.id,
            "draft": draft.id,
            "other_completed": other_completed.id,
            "admin_completed": admin_completed.id,
        }
    engine.dispose()
    return result


async def login(
    client: httpx.AsyncClient,
    username: str = "result-operator",
    password: str = "operator-password",
) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200


def test_logged_in_operator_searches_active_product_options() -> None:
    prepare_product_options()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            anonymous = await client.get(
                "/api/v1/product-options",
                params={"query": "129756", "page": 1, "page_size": 20},
            )
            assert anonymous.status_code == 401

            await login(client)
            by_suffix = await client.get(
                "/api/v1/product-options",
                params={"query": "129756", "page": 1, "page_size": 20},
            )
            assert by_suffix.status_code == 200
            data = by_suffix.json()["data"]
            assert data["total"] == 1
            assert data["page"] == 1
            assert data["page_size"] == 20
            assert [item["carton_code"] for item in data["items"]] == [
                "6901028129756"
            ]
            assert set(data["items"][0]) == {
                "id",
                "carton_code",
                "brand",
                "standard_name",
                "carton_retail_price",
                "sticks_per_pack",
                "packs_per_carton",
            }

            by_name = await client.get(
                "/api/v1/product-options",
                params={"query": "红方印", "page": 1, "page_size": 20},
            )
            assert by_name.status_code == 200
            assert by_name.json()["data"]["total"] == 1

            inactive = await client.get(
                "/api/v1/product-options",
                params={"query": "045919", "page": 1, "page_size": 20},
            )
            assert inactive.status_code == 200
            assert inactive.json()["data"]["items"] == []

            empty = await client.get(
                "/api/v1/product-options",
                params={"query": "", "page": 1, "page_size": 20},
            )
            assert empty.status_code == 200
            assert empty.json()["data"]["items"] == []

    asyncio.run(scenario())


def result_item_payload(product_id: int, *, quantity: str = "1.2") -> dict[str, object]:
    return {
        "request_id": "00000000-0000-4000-8000-000000009001",
        "product_id": product_id,
        "quantity_cartons": quantity,
        "source_allocations": [
            {
                "source_type": "OUTSIDE_PROVINCE",
                "province_name": "天津市",
                "city_name": None,
                "pack_count": int(Decimal(quantity) * 10),
            }
        ],
    }


def test_same_branch_operator_adds_and_replaces_a_completed_result_item() -> None:
    records = prepare_product_options()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            await login(client, "result-coworker", "coworker-password")
            payload = result_item_payload(records["active_product"])
            created = await client.post(
                f"/api/v1/scan-sessions/{records['completed']}/result-items",
                json=payload,
                headers={"Origin": "http://testserver"},
            )
            assert created.status_code == 200
            operation = created.json()["data"]
            assert operation["item"]["total_sticks"] == 240
            assert operation["source_state"]["allocated_pack_count"] == 12
            assert operation["source_state"]["allocations"][0]["city_name"] == "不详"
            assert operation["idempotent_replay"] is False

            replay = await client.post(
                f"/api/v1/scan-sessions/{records['completed']}/result-items",
                json=payload,
                headers={"Origin": "http://testserver"},
            )
            assert replay.status_code == 200
            assert replay.json()["data"]["item"]["total_sticks"] == 240
            assert replay.json()["data"]["idempotent_replay"] is True

            replacement = result_item_payload(records["active_product"], quantity="0.5")
            replacement["request_id"] = "00000000-0000-4000-8000-000000009002"
            replacement.pop("product_id")
            replaced = await client.put(
                f"/api/v1/scan-sessions/{records['completed']}/result-items/"
                f"{records['active_product']}",
                json=replacement,
                headers={"Origin": "http://testserver"},
            )
            assert replaced.status_code == 200
            assert replaced.json()["data"]["item"]["total_sticks"] == 100
            assert replaced.json()["data"]["source_state"]["allocated_pack_count"] == 5

            exported = await client.get(
                f"/api/v1/scan-sessions/{records['completed']}/export.xlsx"
            )
            assert exported.status_code == 200
            sheet = load_workbook(BytesIO(exported.content))["卷烟登记表"]
            header_row = next(
                row for row in range(1, sheet.max_row + 1)
                if sheet.cell(row, 1).value == "序号"
            )
            assert sheet.cell(header_row + 1, 8).value == 0.5
            assert sheet.cell(header_row + 1, 9).value == 100
            assert sheet.cell(header_row + 1, 11).value == "天津市"
            assert sheet.cell(header_row + 1, 12).value == "不详"

    asyncio.run(scenario())


def test_completed_result_correction_enforces_status_role_and_data_scope() -> None:
    records = prepare_product_options()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            payload = result_item_payload(records["active_product"])

            await login(client, "result-viewer", "viewer-password")
            viewer = await client.post(
                f"/api/v1/scan-sessions/{records['completed']}/result-items",
                json=payload,
                headers={"Origin": "http://testserver"},
            )
            assert viewer.status_code == 403

            await login(client, "result-other", "other-password")
            hidden = await client.post(
                f"/api/v1/scan-sessions/{records['completed']}/result-items",
                json=payload,
                headers={"Origin": "http://testserver"},
            )
            assert hidden.status_code == 404

            await login(client)
            admin_hidden = await client.post(
                f"/api/v1/scan-sessions/{records['admin_completed']}/result-items",
                json=payload,
                headers={"Origin": "http://testserver"},
            )
            assert admin_hidden.status_code == 404

            draft = await client.post(
                f"/api/v1/scan-sessions/{records['draft']}/result-items",
                json=payload,
                headers={"Origin": "http://testserver"},
            )
            assert draft.status_code == 409
            assert draft.json()["error"]["code"] == "RESULT_SESSION_NOT_COMPLETED"

            inactive_payload = result_item_payload(records["inactive_product"])
            inactive_payload["request_id"] = "00000000-0000-4000-8000-000000009003"
            inactive = await client.post(
                f"/api/v1/scan-sessions/{records['completed']}/result-items",
                json=inactive_payload,
                headers={"Origin": "http://testserver"},
            )
            assert inactive.status_code == 409
            assert inactive.json()["error"]["code"] == "PRODUCT_INACTIVE"

    asyncio.run(scenario())


def test_completed_result_allows_source_edit_and_delete_but_still_rejects_scan() -> None:
    records = prepare_product_options()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            await login(client)
            payload = result_item_payload(records["active_product"], quantity="0.5")
            created = await client.post(
                f"/api/v1/scan-sessions/{records['completed']}/result-items",
                json=payload,
                headers={"Origin": "http://testserver"},
            )
            assert created.status_code == 200

            source_edit = await client.put(
                f"/api/v1/scan-sessions/{records['completed']}/items/"
                f"{records['active_product']}/source-allocations",
                json={
                    "items": [
                        {
                            "source_type": "OUTSIDE_PROVINCE",
                            "province_name": "福建省",
                            "city_name": None,
                            "pack_count": 5,
                        }
                    ]
                },
                headers={"Origin": "http://testserver"},
            )
            assert source_edit.status_code == 200
            assert source_edit.json()["data"]["allocations"][0]["city_name"] == "不详"

            scan = await client.post(
                f"/api/v1/scan-sessions/{records['completed']}/scan",
                json={
                    "request_id": "00000000-0000-4000-8000-000000009004",
                    "code": "6901028129756",
                },
                headers={"Origin": "http://testserver"},
            )
            assert scan.status_code == 409
            assert scan.json()["error"]["code"] == "SCAN_SESSION_CLOSED"

            removed = await client.post(
                f"/api/v1/scan-sessions/{records['completed']}/items/"
                f"{records['active_product']}/remove",
                json={"request_id": "00000000-0000-4000-8000-000000009005"},
                headers={"Origin": "http://testserver"},
            )
            assert removed.status_code == 200
            assert removed.json()["data"]["state"]["items"] == []
            assert removed.json()["data"]["event"]["delta_sticks"] == -100

    asyncio.run(scenario())
