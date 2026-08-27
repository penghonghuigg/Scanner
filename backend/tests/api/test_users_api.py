import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.db.schema import initialize_database
from app.models.auth import User, UserSession
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def prepare_users() -> None:
    database_url = database_url_for_test()
    initialize_database(database_url)
    engine = create_engine(database_url)
    now = datetime.now(UTC).replace(tzinfo=None)
    with Session(engine) as session, session.begin():
        session.execute(delete(ScanEvent).where(ScanEvent.source_event_id.is_not(None)))
        session.execute(delete(ScanEvent))
        session.execute(delete(ScanSessionItem))
        session.execute(delete(UserSession))
        session.execute(delete(ScanSession))
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


def registration_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "username": " Zhang.San ",
        "display_name": " 张三 ",
        "branch_code": "FENGTAI",
        "password": "initial-password",
        "password_confirmation": "initial-password",
    }
    payload.update(overrides)
    return payload


def test_admin_registers_an_operator_with_a_hashed_password_and_branch() -> None:
    prepare_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            await login(client, "admin", "admin-password")
            response = await client.post(
                "/api/v1/users",
                json=registration_payload(),
                headers={"Origin": "http://testserver"},
            )
            assert response.status_code == 201
            user_data = response.json()["data"]["user"]
            assert isinstance(user_data.pop("id"), int)
            assert user_data == {
                "username": "zhang.san",
                "display_name": "张三",
                "role": "OPERATOR",
                "branch_code": "FENGTAI",
                "branch_name": "凤台县局",
            }

        engine = create_engine(database_url_for_test())
        with Session(engine) as session:
            user = session.scalar(select(User).where(User.username == "zhang.san"))
            assert user is not None
            assert user.password_hash != "initial-password"
            assert verify_password(user.password_hash, "initial-password")
        engine.dispose()

    asyncio.run(scenario())


def test_registration_rejects_duplicate_branch_and_password_errors() -> None:
    prepare_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            await login(client, "admin", "admin-password")
            cases = (
                (registration_payload(username="operator"), 409, "USERNAME_EXISTS"),
                (registration_payload(branch_code="UNKNOWN"), 422, "BRANCH_INVALID"),
                (
                    registration_payload(password_confirmation="different-password"),
                    422,
                    "PASSWORD_MISMATCH",
                ),
                (registration_payload(role="ADMIN"), 422, "VALIDATION_ERROR"),
            )
            for payload, status_code, error_code in cases:
                response = await client.post(
                    "/api/v1/users",
                    json=payload,
                    headers={"Origin": "http://testserver"},
                )
                assert response.status_code == status_code
                assert response.json()["error"]["code"] == error_code

    asyncio.run(scenario())


def test_registration_requires_login_and_admin_permission() -> None:
    prepare_users()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            anonymous = await client.post(
                "/api/v1/users",
                json=registration_payload(),
                headers={"Origin": "http://testserver"},
            )
            assert anonymous.status_code == 401
            assert anonymous.json()["error"]["code"] == "AUTH_REQUIRED"

            await login(client, "operator", "operator-password")
            forbidden = await client.post(
                "/api/v1/users",
                json=registration_payload(),
                headers={"Origin": "http://testserver"},
            )
            assert forbidden.status_code == 403
            assert forbidden.json()["error"]["code"] == "FORBIDDEN"

    asyncio.run(scenario())
