import asyncio
import hashlib
import os
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openpyxl import load_workbook
from sqlalchemy import create_engine, delete, select
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


def prepare_records() -> dict[str, int]:
    initialize_database(database_url_for_test())
    engine = create_engine(database_url_for_test())
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
        admin = User(
            username="final-admin",
            password_hash=hash_password("admin-password"),
            display_name="系统管理员",
            role="ADMIN",
            branch_code=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        operator = User(
            username="final-operator",
            password_hash=hash_password("operator-password"),
            display_name="凤台操作员",
            role="OPERATOR",
            branch_code="FENGTAI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        viewer = User(
            username="final-viewer",
            password_hash=hash_password("viewer-password"),
            display_name="凤台查看员",
            role="VIEWER",
            branch_code="FENGTAI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        other = User(
            username="final-other",
            password_hash=hash_password("other-password"),
            display_name="潘集操作员",
            role="OPERATOR",
            branch_code="PANJI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        product = CigaretteProduct(
            carton_code="6900000060711",
            pack_code="6900000060712",
            brand="测试品牌",
            standard_name="接口来源卷烟",
            carton_retail_price=Decimal("100.00"),
            sticks_per_pack=20,
            packs_per_carton=10,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([admin, operator, viewer, other, product])
        session.flush()
        batch = ScanSession(
            session_no="PD20260902-150000-6071",
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
        session.add(batch)
        session.flush()
        item = ScanSessionItem(
            session_id=batch.id,
            product_id=product.id,
            carton_count=1,
            pack_count=8,
            manual_delta_sticks=0,
            total_sticks=360,
            product_snapshot={
                "product_id": product.id,
                "carton_code": product.carton_code,
                "pack_code": product.pack_code,
                "brand": product.brand,
                "standard_name": product.standard_name,
                "carton_retail_price": "100.00",
                "sticks_per_pack": 20,
                "packs_per_carton": 10,
                "sticks_per_carton": 200,
            },
            updated_at=now,
        )
        session.add(item)
        session.flush()
        result = {"batch": batch.id, "product": product.id, "operator": operator.id}
    engine.dispose()
    return result


async def login(client: httpx.AsyncClient, username: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200


def test_regions_require_login_and_return_clean_catalog() -> None:
    prepare_records()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            unauthorized = await client.get("/api/v1/regions")
            await login(client, "final-operator", "operator-password")
            response = await client.get("/api/v1/regions")

            assert unauthorized.status_code == 401
            assert response.status_code == 200
            data = response.json()["data"]
            assert [item["label"] for item in data["source_types"]] == [
                "外省流入",
                "来源不详",
                "市内串码",
                "省内市外",
            ]
            province_names = [item["name"] for item in data["provinces"]]
            assert "安徽省" in province_names
            assert "香港特别行政区" not in province_names
            assert "澳门特别行政区" not in province_names

    asyncio.run(scenario())


def test_operator_replaces_and_reads_sources_while_viewer_cannot_write() -> None:
    records = prepare_records()
    source_path = (
        f"/api/v1/scan-sessions/{records['batch']}/items/"
        f"{records['product']}/source-allocations"
    )
    list_path = f"/api/v1/scan-sessions/{records['batch']}/source-allocations"
    payload = {
        "items": [
            {
                "source_type": "OUTSIDE_PROVINCE",
                "province_name": "天津市",
                "city_name": "天津市",
                "pack_count": 15,
            },
            {"source_type": "UNKNOWN", "pack_count": 3},
        ]
    }

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "final-operator", "operator-password")
            saved = await client.put(
                source_path,
                json=payload,
                headers={"Origin": "http://testserver"},
            )
            listed = await client.get(list_path)
            assert saved.status_code == 200
            assert saved.json()["data"]["allocated_pack_count"] == 18
            assert listed.status_code == 200
            assert listed.json()["data"]["items"][0]["remaining_pack_count"] == 0

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as viewer_client:
            await login(viewer_client, "final-viewer", "viewer-password")
            forbidden = await viewer_client.put(
                source_path,
                json=payload,
                headers={"Origin": "http://testserver"},
            )
            assert forbidden.status_code == 403
            assert forbidden.json()["error"]["code"] == "FORBIDDEN"

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as other_client:
            await login(other_client, "final-other", "other-password")
            hidden = await other_client.get(list_path)
            assert hidden.status_code == 404
            assert hidden.json()["error"]["code"] == "SCAN_SESSION_NOT_FOUND"

    asyncio.run(scenario())


def test_source_api_rejects_invalid_location_and_quantity_mismatch() -> None:
    records = prepare_records()
    path = (
        f"/api/v1/scan-sessions/{records['batch']}/items/"
        f"{records['product']}/source-allocations"
    )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "final-operator", "operator-password")
            invalid_location = await client.put(
                path,
                json={
                    "items": [
                        {
                            "source_type": "OUTSIDE_PROVINCE",
                            "province_name": "安徽省",
                            "city_name": "合肥市",
                            "pack_count": 18,
                        }
                    ]
                },
                headers={"Origin": "http://testserver"},
            )
            mismatch = await client.put(
                path,
                json={"items": [{"source_type": "UNKNOWN", "pack_count": 17}]},
                headers={"Origin": "http://testserver"},
            )
            assert invalid_location.status_code == 422
            assert invalid_location.json()["error"]["code"] == "SOURCE_LOCATION_INVALID"
            assert mismatch.status_code == 422
            assert mismatch.json()["error"]["code"] == "SOURCE_QUANTITY_MISMATCH"

    asyncio.run(scenario())


def test_complete_requires_sources_and_exception_confirmation_then_allows_source_correction(
) -> None:
    records = prepare_records()
    complete_path = f"/api/v1/scan-sessions/{records['batch']}/complete"
    source_path = (
        f"/api/v1/scan-sessions/{records['batch']}/items/"
        f"{records['product']}/source-allocations"
    )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "final-operator", "operator-password")
            missing_sources = await client.post(
                complete_path,
                json={"confirm_exceptions": False},
                headers={"Origin": "http://testserver"},
            )
            assert missing_sources.status_code == 409
            assert missing_sources.json()["error"]["code"] == (
                "SOURCE_ALLOCATION_REQUIRED"
            )

            saved = await client.put(
                source_path,
                json={"items": [{"source_type": "UNKNOWN", "pack_count": 18}]},
                headers={"Origin": "http://testserver"},
            )
            assert saved.status_code == 200

            engine = create_engine(database_url_for_test())
            with Session(engine) as session, session.begin():
                session.add(
                    ScanEvent(
                        request_id="00000000-0000-4000-8000-000000006201",
                        session_id=records["batch"],
                        event_type="SCAN",
                        result="UNKNOWN",
                        raw_code="6999999999981",
                        product_id=None,
                        unit_type=None,
                        delta_sticks=0,
                        source_event_id=None,
                        reason=None,
                        candidate_snapshot=None,
                        product_snapshot=None,
                        operator_id=records["operator"],
                        created_at=datetime.now(UTC).replace(tzinfo=None),
                    )
                )
            engine.dispose()

            needs_confirmation = await client.post(
                complete_path,
                json={"confirm_exceptions": False},
                headers={"Origin": "http://testserver"},
            )
            completed = await client.post(
                complete_path,
                json={"confirm_exceptions": True},
                headers={"Origin": "http://testserver"},
            )
            repeated = await client.post(
                complete_path,
                json={"confirm_exceptions": True},
                headers={"Origin": "http://testserver"},
            )
            corrected_source = await client.put(
                source_path,
                json={"items": [{"source_type": "UNKNOWN", "pack_count": 18}]},
                headers={"Origin": "http://testserver"},
            )

            assert needs_confirmation.status_code == 409
            assert needs_confirmation.json()["error"]["code"] == (
                "EXCEPTION_CONFIRMATION_REQUIRED"
            )
            assert completed.status_code == 200
            assert completed.json()["data"]["scan_session"]["status"] == "COMPLETED"
            assert completed.json()["data"]["unknown_count"] == 1
            assert completed.json()["data"]["unresolved_ambiguity_count"] == 0
            assert repeated.status_code == 200
            assert repeated.json()["data"]["scan_session"]["completed_at"] == (
                completed.json()["data"]["scan_session"]["completed_at"]
            )
            assert corrected_source.status_code == 200
            assert corrected_source.json()["data"]["allocated_pack_count"] == 18

    asyncio.run(scenario())


def test_export_requires_completed_batch_and_records_the_in_memory_file() -> None:
    records = prepare_records()
    export_path = f"/api/v1/scan-sessions/{records['batch']}/export.xlsx"
    source_path = (
        f"/api/v1/scan-sessions/{records['batch']}/items/"
        f"{records['product']}/source-allocations"
    )
    complete_path = f"/api/v1/scan-sessions/{records['batch']}/complete"

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "final-operator", "operator-password")
            draft_export = await client.get(export_path)
            assert draft_export.status_code == 409
            assert draft_export.json()["error"]["code"] == (
                "EXPORT_SESSION_NOT_COMPLETED"
            )

            await client.put(
                source_path,
                json={
                    "items": [
                        {
                            "source_type": "OUTSIDE_PROVINCE",
                            "province_name": "天津市",
                            "city_name": "天津市",
                            "pack_count": 15,
                        },
                        {"source_type": "UNKNOWN", "pack_count": 3},
                    ]
                },
                headers={"Origin": "http://testserver"},
            )
            completed = await client.post(
                complete_path,
                json={"confirm_exceptions": False},
                headers={"Origin": "http://testserver"},
            )
            assert completed.status_code == 200

            exported = await client.get(export_path)
            assert exported.status_code == 200
            assert exported.headers["content-type"].startswith(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            assert "PD20260902-150000-6071" in exported.headers["content-disposition"]
            assert exported.content[:2] == b"PK"
            workbook = load_workbook(BytesIO(exported.content))
            assert workbook.sheetnames == [
                "卷烟登记表",
                "品规汇总",
                "操作流水",
                "异常编码",
            ]

            engine = create_engine(database_url_for_test())
            with Session(engine) as session:
                record = session.scalar(select(ExportRecord))
                assert record is not None
                assert record.file_size == len(exported.content)
                assert record.file_sha256 == hashlib.sha256(exported.content).hexdigest()
                assert record.generated_by == records["operator"]
            engine.dispose()

    asyncio.run(scenario())
