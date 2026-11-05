import asyncio
from datetime import datetime
from types import SimpleNamespace

import httpx

from app.api.dependencies import get_current_user, get_database_session
from app.core.config import Settings
from app.schemas.auth import AuthUser


def make_app():
    from app.main import create_app

    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
            allowed_origins="http://testserver",
            jiandaoyun_create_url="https://example.test/create",
            jiandaoyun_app_id="test-app",
            jiandaoyun_entry_id="test-entry",
            jiandaoyun_api_key="test-key",
        )
    )
    app.dependency_overrides[get_current_user] = lambda: AuthUser(
        id=7,
        username="operator",
        display_name="张三",
        role="OPERATOR",
        branch_code="FENGTAI",
        branch_name="凤台县局",
    )
    app.dependency_overrides[get_database_session] = lambda: object()
    return app


def snapshot(status: str = "SUCCEEDED") -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        external_data_id="external-id" if status == "SUCCEEDED" else None,
        attempt_count=1,
        last_error_code=None,
        last_error_message=None,
        created_at=datetime(2026, 9, 4, 4, 0, 0),
        updated_at=datetime(2026, 9, 4, 4, 0, 1),
        succeeded_at=datetime(2026, 9, 4, 4, 0, 1)
        if status == "SUCCEEDED"
        else None,
        payload_json={"must": "not leak"},
        payload_sha256="0" * 64,
    )


def test_get_snapshot_returns_null_without_leaking_payload(monkeypatch) -> None:
    import app.api.v1.integration as route

    monkeypatch.setattr(route, "get_integration_snapshot", lambda *_args, **_kwargs: None)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/v1/scan-sessions/42/integration-snapshot")

        assert response.status_code == 200
        assert response.json()["data"] == {"snapshot": None}
        assert response.json()["trace_id"]

    asyncio.run(scenario())


def test_integration_snapshot_requires_login() -> None:
    from app.main import create_app

    app = create_app(
        Settings(
            app_env="test",
            database_url="mysql+pymysql://unused:unused@127.0.0.1:3306/unused",
            cookie_secure=False,
        )
    )

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get(
                "/api/v1/scan-sessions/42/integration-snapshot"
            )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "AUTH_REQUIRED"

    asyncio.run(scenario())


def test_post_import_requires_origin_and_returns_safe_snapshot(monkeypatch) -> None:
    import app.api.v1.integration as route

    calls = 0

    def fake_import(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return snapshot()

    monkeypatch.setattr(route, "import_completed_session", fake_import)

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()),
            base_url="http://testserver",
        ) as client:
            missing_origin = await client.post(
                "/api/v1/scan-sessions/42/jiandaoyun-import"
            )
            response = await client.post(
                "/api/v1/scan-sessions/42/jiandaoyun-import",
                headers={"Origin": "http://testserver"},
            )

        assert missing_origin.status_code == 403
        assert missing_origin.json()["error"]["code"] == "ORIGIN_NOT_ALLOWED"
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["snapshot"]["status"] == "SUCCEEDED"
        assert body["data"]["snapshot"]["external_data_id"] == "external-id"
        assert "payload_json" not in body["data"]["snapshot"]
        assert "payload_sha256" not in body["data"]["snapshot"]
        assert calls == 1

    asyncio.run(scenario())


def test_post_import_rejects_incomplete_configuration(monkeypatch) -> None:
    import app.api.v1.integration as route

    monkeypatch.setattr(
        route,
        "import_completed_session",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("不得调用服务")),
    )
    app = make_app()
    app.state.settings.jiandaoyun_api_key = ""

    async def scenario() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/api/v1/scan-sessions/42/jiandaoyun-import",
                headers={"Origin": "http://testserver"},
            )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INTEGRATION_NOT_CONFIGURED"

    asyncio.run(scenario())


def test_integration_errors_use_stable_error_codes(monkeypatch) -> None:
    import app.api.v1.integration as route
    from app.integrations.jiandaoyun import ExternalRejectedError
    from app.integrations.service import IntegrationInProgressError

    errors = [
        (IntegrationInProgressError("正在导入"), 409, "INTEGRATION_IN_PROGRESS"),
        (ExternalRejectedError("HTTP 422"), 502, "INTEGRATION_EXTERNAL_REJECTED"),
    ]

    async def scenario() -> None:
        for error, expected_status, expected_code in errors:
            monkeypatch.setattr(
                route,
                "import_completed_session",
                lambda *_args, _error=error, **_kwargs: (_ for _ in ()).throw(_error),
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=make_app()),
                base_url="http://testserver",
            ) as client:
                response = await client.post(
                    "/api/v1/scan-sessions/42/jiandaoyun-import",
                    headers={"Origin": "http://testserver"},
                )
            assert response.status_code == expected_status
            assert response.json()["error"]["code"] == expected_code

    asyncio.run(scenario())
