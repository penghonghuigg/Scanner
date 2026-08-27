import asyncio
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.models.auth import User, UserSession
from app.models.catalog import CigaretteProduct
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
        session.execute(delete(ScanEvent).where(ScanEvent.source_event_id.is_not(None)))
        session.execute(delete(ScanEvent))
        session.execute(delete(ScanSessionItem))
        session.execute(delete(UserSession))
        session.execute(delete(ScanSession))
        session.execute(delete(CigaretteProduct))
        session.execute(delete(User))
        admin = User(
            username="admin",
            password_hash=hash_password("admin-password"),
            display_name="系统管理员",
            role="ADMIN",
            branch_code=None,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        operator = User(
            username="operator",
            password_hash=hash_password("operator-password"),
            display_name="凤台人员",
            role="OPERATOR",
            branch_code="FENGTAI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        viewer = User(
            username="viewer",
            password_hash=hash_password("viewer-password"),
            display_name="凤台查看员",
            role="VIEWER",
            branch_code="FENGTAI",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add_all([admin, operator, viewer])
        session.flush()
        unique = CigaretteProduct(
            carton_code="6900000000101",
            pack_code="6900000000102",
            brand="测试品牌",
            standard_name="接口品规",
            carton_retail_price=Decimal("100.00"),
            sticks_per_pack=20,
            packs_per_carton=10,
            is_active=True,
        )
        candidate_one = CigaretteProduct(
            carton_code="6900000000103",
            pack_code="6900000000109",
            brand="测试品牌",
            standard_name="接口候选一",
            carton_retail_price=Decimal("110.00"),
            sticks_per_pack=20,
            packs_per_carton=10,
            is_active=True,
        )
        candidate_two = CigaretteProduct(
            carton_code="6900000000104",
            pack_code="6900000000109",
            brand="测试品牌",
            standard_name="接口候选二",
            carton_retail_price=Decimal("120.00"),
            sticks_per_pack=20,
            packs_per_carton=10,
            is_active=True,
        )
        session.add_all([unique, candidate_one, candidate_two])
        session.flush()
        operator_batch = ScanSession(
            session_no="PD20260827-230000-0101",
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
        admin_batch = ScanSession(
            session_no="PD20260827-230000-0102",
            business_type="MARKET_INSPECTION",
            filing_case_no=None,
            location=None,
            notes=None,
            branch_code="FENGTAI",
            operator_id=admin.id,
            status="DRAFT",
            completed_at=None,
            created_at=now,
            updated_at=now,
        )
        session.add_all([operator_batch, admin_batch])
        session.flush()
        result = {
            "operator_batch": operator_batch.id,
            "admin_batch": admin_batch.id,
            "unique": unique.id,
            "candidate_one": candidate_one.id,
        }
    engine.dispose()
    return result


async def login(client: httpx.AsyncClient, username: str, password: str) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200


def test_operator_scans_replays_reads_state_and_resolves_ambiguity() -> None:
    records = prepare_records()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "operator", "operator-password")
            request = {
                "request_id": "00000000-0000-4000-8000-000000000101",
                "code": "6900000000101",
            }
            scanned = await client.post(
                f"/api/v1/scan-sessions/{records['operator_batch']}/scan",
                json=request,
                headers={"Origin": "http://testserver"},
            )
            replay = await client.post(
                f"/api/v1/scan-sessions/{records['operator_batch']}/scan",
                json=request,
                headers={"Origin": "http://testserver"},
            )
            assert scanned.status_code == 200
            assert scanned.json()["data"]["event"]["result"] == "SUCCESS"
            assert scanned.json()["data"]["state"]["summary"]["total_sticks"] == 200
            assert replay.json()["data"]["idempotent_replay"] is True
            assert replay.json()["data"]["state"]["summary"]["total_sticks"] == 200

            ambiguous = await client.post(
                f"/api/v1/scan-sessions/{records['operator_batch']}/scan",
                json={
                    "request_id": "00000000-0000-4000-8000-000000000102",
                    "code": "6900000000109",
                },
                headers={"Origin": "http://testserver"},
            )
            ambiguous_event = ambiguous.json()["data"]["event"]
            assert ambiguous_event["result"] == "AMBIGUOUS"
            assert len(ambiguous_event["candidate_snapshot"]) == 2

            resolved = await client.post(
                f"/api/v1/scan-sessions/{records['operator_batch']}/resolve",
                json={
                    "request_id": "00000000-0000-4000-8000-000000000103",
                    "event_id": ambiguous_event["id"],
                    "product_id": records["candidate_one"],
                },
                headers={"Origin": "http://testserver"},
            )
            state = await client.get(
                f"/api/v1/scan-sessions/{records['operator_batch']}/scan-state"
            )
            assert resolved.status_code == 200
            assert resolved.json()["data"]["event"]["event_type"] == "RESOLVE"
            assert state.status_code == 200
            assert state.json()["data"]["summary"] == {
                "product_count": 2,
                "carton_count": 1,
                "pack_count": 1,
                "total_sticks": 220,
                "unknown_count": 0,
                "ambiguous_count": 0,
            }

    asyncio.run(scenario())


def test_old_request_replays_even_after_it_leaves_recent_event_window() -> None:
    records = prepare_records()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "operator", "operator-password")
            path = f"/api/v1/scan-sessions/{records['operator_batch']}/scan"
            original = {
                "request_id": "00000000-0000-4000-8000-000000000201",
                "code": "6900000000101",
            }
            created = await client.post(
                path,
                json=original,
                headers={"Origin": "http://testserver"},
            )
            assert created.status_code == 200

            for index in range(202, 253):
                response = await client.post(
                    path,
                    json={
                        "request_id": f"00000000-0000-4000-8000-{index:012d}",
                        "code": "6999999999999",
                    },
                    headers={"Origin": "http://testserver"},
                )
                assert response.status_code == 200

            replay = await client.post(
                path,
                json=original,
                headers={"Origin": "http://testserver"},
            )
            assert replay.status_code == 200
            assert replay.json()["data"]["idempotent_replay"] is True
            assert replay.json()["data"]["event"]["request_id"] == original["request_id"]
            assert replay.json()["data"]["state"]["summary"]["total_sticks"] == 200

    asyncio.run(scenario())


def test_scanning_errors_origin_and_data_scope_are_enforced() -> None:
    records = prepare_records()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "operator", "operator-password")
            no_origin = await client.post(
                f"/api/v1/scan-sessions/{records['operator_batch']}/scan",
                json={
                    "request_id": "00000000-0000-4000-8000-000000000111",
                    "code": "6900000000101",
                },
            )
            invalid_responses = []
            for offset, invalid_code in enumerate(
                ("690000000101", "69000000000101", "69000000000000101", "ABC"),
                start=112,
            ):
                invalid_responses.append(
                    await client.post(
                        f"/api/v1/scan-sessions/{records['operator_batch']}/scan",
                        json={
                            "request_id": f"00000000-0000-4000-8000-{offset:012d}",
                            "code": invalid_code,
                        },
                        headers={"Origin": "http://testserver"},
                    )
                )
            hidden_state = await client.get(
                f"/api/v1/scan-sessions/{records['admin_batch']}/scan-state"
            )
            hidden_write = await client.post(
                f"/api/v1/scan-sessions/{records['admin_batch']}/scan",
                json={
                    "request_id": "00000000-0000-4000-8000-000000000113",
                    "code": "6900000000101",
                },
                headers={"Origin": "http://testserver"},
            )
            assert (no_origin.status_code, no_origin.json()["error"]["code"]) == (
                403,
                "ORIGIN_NOT_ALLOWED",
            )
            assert [
                (response.status_code, response.json()["error"]["code"])
                for response in invalid_responses
            ] == [(422, "BARCODE_INVALID")] * 4
            assert hidden_state.status_code == 404
            assert hidden_write.status_code == 404

            await login(client, "viewer", "viewer-password")
            readable = await client.get(
                f"/api/v1/scan-sessions/{records['operator_batch']}/scan-state"
            )
            forbidden = await client.post(
                f"/api/v1/scan-sessions/{records['operator_batch']}/scan",
                json={
                    "request_id": "00000000-0000-4000-8000-000000000114",
                    "code": "6900000000101",
                },
                headers={"Origin": "http://testserver"},
            )
            assert readable.status_code == 200
            assert forbidden.status_code == 403
            assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    asyncio.run(scenario())


def test_scanning_conflicts_and_closed_session_map_to_spec_errors() -> None:
    records = prepare_records()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "operator", "operator-password")
            scan_path = f"/api/v1/scan-sessions/{records['operator_batch']}/scan"
            resolve_path = f"/api/v1/scan-sessions/{records['operator_batch']}/resolve"
            request_id = "00000000-0000-4000-8000-000000000121"
            created = await client.post(
                scan_path,
                json={"request_id": request_id, "code": "6900000000101"},
                headers={"Origin": "http://testserver"},
            )
            conflict = await client.post(
                scan_path,
                json={"request_id": request_id, "code": "6900000000102"},
                headers={"Origin": "http://testserver"},
            )
            assert created.status_code == 200
            assert (conflict.status_code, conflict.json()["error"]["code"]) == (
                409,
                "IDEMPOTENCY_CONFLICT",
            )

            ambiguous = await client.post(
                scan_path,
                json={
                    "request_id": "00000000-0000-4000-8000-000000000122",
                    "code": "6900000000109",
                },
                headers={"Origin": "http://testserver"},
            )
            event_id = ambiguous.json()["data"]["event"]["id"]
            invalid_candidate = await client.post(
                resolve_path,
                json={
                    "request_id": "00000000-0000-4000-8000-000000000123",
                    "event_id": event_id,
                    "product_id": records["unique"],
                },
                headers={"Origin": "http://testserver"},
            )
            resolved = await client.post(
                resolve_path,
                json={
                    "request_id": "00000000-0000-4000-8000-000000000124",
                    "event_id": event_id,
                    "product_id": records["candidate_one"],
                },
                headers={"Origin": "http://testserver"},
            )
            resolved_twice = await client.post(
                resolve_path,
                json={
                    "request_id": "00000000-0000-4000-8000-000000000125",
                    "event_id": event_id,
                    "product_id": records["candidate_one"],
                },
                headers={"Origin": "http://testserver"},
            )
            assert invalid_candidate.json()["error"]["code"] == ("AMBIGUITY_CANDIDATE_INVALID")
            assert resolved.status_code == 200
            assert resolved_twice.json()["error"]["code"] == ("AMBIGUITY_ALREADY_RESOLVED")

            engine = create_engine(database_url_for_test())
            with Session(engine) as session, session.begin():
                batch = session.get(ScanSession, records["operator_batch"])
                assert batch is not None
                batch.status = "COMPLETED"
            engine.dispose()
            closed = await client.post(
                scan_path,
                json={
                    "request_id": "00000000-0000-4000-8000-000000000126",
                    "code": "6900000000101",
                },
                headers={"Origin": "http://testserver"},
            )
            assert (closed.status_code, closed.json()["error"]["code"]) == (
                409,
                "SCAN_SESSION_CLOSED",
            )

    asyncio.run(scenario())
