import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.models.auth import User, UserSession
from app.models.finalization import ExportRecord, ScanItemSourceAllocation
from app.models.integration import IntegrationSnapshot
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RESPONSE_FIELDS = {
    "id",
    "session_no",
    "business_type",
    "business_type_name",
    "filing_case_no",
    "location",
    "notes",
    "branch_code",
    "branch_name",
    "operator_id",
    "operator_name",
    "status",
    "status_name",
    "completed_at",
    "product_count",
    "total_sticks",
    "display_label",
    "created_at",
    "updated_at",
}


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def user_model(
    username: str,
    password: str,
    display_name: str,
    role: str,
    branch_code: str | None,
    now: datetime,
) -> User:
    return User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
        branch_code=branch_code,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def prepare_users() -> None:
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
        session.execute(delete(User))
        session.add_all(
            [
                user_model("admin", "admin-password", "系统管理员", "ADMIN", None, now),
                user_model(
                    "operator",
                    "operator-password",
                    "凤台人员",
                    "OPERATOR",
                    "FENGTAI",
                    now,
                ),
                user_model(
                    "panji",
                    "operator-password",
                    "潘集人员",
                    "OPERATOR",
                    "PANJI",
                    now,
                ),
                user_model(
                    "viewer",
                    "viewer-password",
                    "凤台查看员",
                    "VIEWER",
                    "FENGTAI",
                    now,
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


def batch_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "business_type": "MARKET_INSPECTION",
        "filing_case_no": " 凤烟立〔2026〕001号 ",
        "location": "凤台县城区",
        "notes": " ",
        "branch_code": "FENGTAI",
    }
    payload.update(overrides)
    return payload


def test_admin_creates_lists_and_reads_a_scan_session() -> None:
    prepare_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "admin", "admin-password")
            created = await client.post(
                "/api/v1/scan-sessions",
                json=batch_payload(),
                headers={"Origin": "http://testserver"},
            )
            assert created.status_code == 201
            scan_session = created.json()["data"]["scan_session"]
            assert set(scan_session) == RESPONSE_FIELDS
            assert scan_session["session_no"].startswith("PD")
            assert scan_session["business_type_name"] == "市场检查"
            assert scan_session["filing_case_no"] == "凤烟立〔2026〕001号"
            assert scan_session["notes"] is None
            assert scan_session["branch_name"] == "凤台县局"
            assert scan_session["status"] == "DRAFT"
            assert scan_session["status_name"] == "进行中"
            assert scan_session["product_count"] == 0
            assert scan_session["total_sticks"] == 0

            listing = await client.get("/api/v1/scan-sessions", params={"branch_code": "FENGTAI"})
            assert listing.status_code == 200
            assert listing.json()["data"]["total"] == 1

            detail = await client.get(f"/api/v1/scan-sessions/{scan_session['id']}")
            assert detail.status_code == 200
            assert detail.json()["data"]["scan_session"]["id"] == scan_session["id"]

    asyncio.run(scenario())


def test_operator_cannot_escape_branch_scope() -> None:
    prepare_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "operator", "operator-password")
            created = await client.post(
                "/api/v1/scan-sessions",
                json=batch_payload(branch_code="PANJI"),
                headers={"Origin": "http://testserver"},
            )
            assert created.status_code == 201
            assert created.json()["data"]["scan_session"]["branch_code"] == "FENGTAI"
            own_id = created.json()["data"]["scan_session"]["id"]

            await login(client, "panji", "operator-password")
            listing = await client.get("/api/v1/scan-sessions")
            hidden = await client.get(f"/api/v1/scan-sessions/{own_id}")
            assert listing.json()["data"]["total"] == 0
            assert hidden.status_code == 404
            assert hidden.json()["error"]["code"] == "SCAN_SESSION_NOT_FOUND"

    asyncio.run(scenario())


def test_branch_user_cannot_list_or_read_admin_created_session() -> None:
    prepare_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "admin", "admin-password")
            admin_created = await client.post(
                "/api/v1/scan-sessions",
                json=batch_payload(branch_code="FENGTAI"),
                headers={"Origin": "http://testserver"},
            )
            assert admin_created.status_code == 201
            admin_session_id = admin_created.json()["data"]["scan_session"]["id"]

            await login(client, "operator", "operator-password")
            operator_created = await client.post(
                "/api/v1/scan-sessions",
                json=batch_payload(),
                headers={"Origin": "http://testserver"},
            )
            assert operator_created.status_code == 201
            operator_session_id = operator_created.json()["data"]["scan_session"]["id"]

            listing = await client.get("/api/v1/scan-sessions")
            hidden_detail = await client.get(f"/api/v1/scan-sessions/{admin_session_id}")

            assert listing.status_code == 200
            assert listing.json()["data"]["total"] == 1
            assert [item["id"] for item in listing.json()["data"]["items"]] == [operator_session_id]
            assert hidden_detail.status_code == 404
            assert hidden_detail.json()["error"]["code"] == "SCAN_SESSION_NOT_FOUND"

            await login(client, "admin", "admin-password")
            admin_listing = await client.get("/api/v1/scan-sessions")
            assert admin_listing.json()["data"]["total"] == 2

    asyncio.run(scenario())


def test_viewer_is_read_only_and_anonymous_access_is_rejected() -> None:
    prepare_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            anonymous = await client.get("/api/v1/scan-sessions")
            assert anonymous.status_code == 401

            await login(client, "viewer", "viewer-password")
            listing = await client.get("/api/v1/scan-sessions")
            forbidden = await client.post(
                "/api/v1/scan-sessions",
                json=batch_payload(),
                headers={"Origin": "http://testserver"},
            )
            assert listing.status_code == 200
            assert forbidden.status_code == 403
            assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    asyncio.run(scenario())


def test_create_validates_origin_business_type_and_admin_branch() -> None:
    prepare_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "admin", "admin-password")
            no_origin = await client.post("/api/v1/scan-sessions", json=batch_payload())
            invalid_type = await client.post(
                "/api/v1/scan-sessions",
                json=batch_payload(business_type="UNKNOWN"),
                headers={"Origin": "http://testserver"},
            )
            missing_branch = await client.post(
                "/api/v1/scan-sessions",
                json=batch_payload(branch_code=None),
                headers={"Origin": "http://testserver"},
            )
            invalid_branch = await client.post(
                "/api/v1/scan-sessions",
                json=batch_payload(branch_code="UNKNOWN"),
                headers={"Origin": "http://testserver"},
            )

            assert (no_origin.status_code, no_origin.json()["error"]["code"]) == (
                403,
                "ORIGIN_NOT_ALLOWED",
            )
            assert invalid_type.json()["error"]["code"] == "BUSINESS_TYPE_INVALID"
            assert missing_branch.json()["error"]["code"] == "BRANCH_REQUIRED"
            assert invalid_branch.json()["error"]["code"] == "BRANCH_INVALID"

    asyncio.run(scenario())


def test_create_maps_exhausted_number_collisions_to_service_unavailable(monkeypatch) -> None:
    from app.api.v1 import scan_sessions
    from app.scanning.service import ScanSessionCreateFailedError

    prepare_users()

    def fail_create(*args, **kwargs):
        raise ScanSessionCreateFailedError("批次创建失败，请重试")

    monkeypatch.setattr(scan_sessions, "create_scan_session", fail_create)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://testserver"
        ) as client:
            await login(client, "admin", "admin-password")
            response = await client.post(
                "/api/v1/scan-sessions",
                json=batch_payload(),
                headers={"Origin": "http://testserver"},
            )
            assert response.status_code == 503
            assert response.json()["error"]["code"] == "SCAN_SESSION_CREATE_FAILED"

    asyncio.run(scenario())
