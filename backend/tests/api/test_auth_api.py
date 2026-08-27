import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_password
from app.db.schema import initialize_database
from app.models.auth import User, UserSession
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def prepare_user(*, active: bool = True) -> None:
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
        session.add(
            User(
                username="admin",
                password_hash=hash_password("correct-password"),
                display_name="系统管理员",
                role="ADMIN",
                is_active=active,
                created_at=now,
                updated_at=now,
            )
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


def test_login_me_and_logout_form_a_cookie_session_lifecycle() -> None:
    prepare_user()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            login = await client.post(
                "/api/v1/auth/login",
                json={"username": " ADMIN ", "password": "correct-password"},
                headers={"Origin": "http://testserver"},
            )
            assert login.status_code == 200
            assert login.json()["data"]["user"]["username"] == "admin"
            assert login.json()["data"]["user"]["role"] == "ADMIN"
            assert login.json()["data"]["user"]["branch_code"] is None
            assert login.json()["data"]["user"]["branch_name"] is None
            assert client.cookies.get("scanner_session")

            me = await client.get("/api/v1/auth/me")
            assert me.status_code == 200
            assert me.json()["data"]["user"]["display_name"] == "系统管理员"
            assert me.json()["data"]["user"]["branch_code"] is None

            logout = await client.post(
                "/api/v1/auth/logout",
                headers={"Origin": "http://testserver"},
            )
            assert logout.status_code == 200
            assert (await client.get("/api/v1/auth/me")).status_code == 401

    asyncio.run(scenario())


def test_invalid_and_inactive_users_share_the_same_public_error() -> None:
    prepare_user(active=False)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            for username, password in (
                ("missing", "wrong-password"),
                ("admin", "wrong-password"),
                ("admin", "correct-password"),
            ):
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"username": username, "password": password},
                    headers={"Origin": "http://testserver"},
                )
                assert response.status_code == 401
                assert response.json()["error"]["code"] == "AUTH_INVALID_CREDENTIALS"

    asyncio.run(scenario())


def test_expired_session_is_rejected() -> None:
    prepare_user()

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            await client.post(
                "/api/v1/auth/login",
                json={"username": "admin", "password": "correct-password"},
                headers={"Origin": "http://testserver"},
            )

            engine = create_engine(database_url_for_test())
            with Session(engine) as session, session.begin():
                session.execute(
                    update(UserSession).values(
                        expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
                    )
                )
            engine.dispose()

            response = await client.get("/api/v1/auth/me")
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "AUTH_REQUIRED"

    asyncio.run(scenario())
