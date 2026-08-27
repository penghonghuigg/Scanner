import asyncio

import httpx
import pytest


def test_live_health_uses_the_standard_success_envelope() -> None:
    try:
        from app.main import create_app
    except ModuleNotFoundError:
        pytest.fail("app.main 尚未实现")

    async def request_live_health() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/health/live")

    response = asyncio.run(request_live_health())

    payload = response.json()
    assert response.status_code == 200
    assert set(payload) == {"success", "data", "trace_id"}
    assert payload["success"] is True
    assert payload["data"] == {"status": "ok"}
    assert response.headers["X-Trace-ID"] == payload["trace_id"]
