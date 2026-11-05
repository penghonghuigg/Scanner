import json
from decimal import Decimal

import httpx
import pytest

from app.integrations.jiandaoyun import (
    BARCODE_WIDGET,
    IDENTIFIER_WIDGET,
    ITEMS_WIDGET,
    QUANTITY_WIDGET,
    TYPE_WIDGET,
    ExternalRejectedError,
    ExternalUncertainError,
    JianDaoYunConfig,
    build_registration_data,
    create_registration,
    payload_sha256,
)

CREATE_URL = "https://example.test/api/v5/app/entry/data/create"
API_KEY = "test-api-key-that-must-not-leak"


def export_data_fixture() -> dict[str, object]:
    return {
        "session": {
            "display_label": "2026-09-04 12:00—张三—2个品规—220支卷烟",
            "branch_name": "凤台县局",
            "filing_case_no": None,
            "operator_name": "张三",
        },
        "items": [
            {
                "product_snapshot": {
                    "carton_code": "6900000000001",
                    "standard_name": "测试卷烟",
                    "brand": "测试品牌",
                    "sticks_per_carton": 200,
                },
                "total_sticks": 200,
                "equivalent_cartons": Decimal("1.0"),
            },
            {
                "product_snapshot": {
                    "carton_code": "6900000000002",
                    "standard_name": "测试卷烟",
                    "brand": "测试品牌",
                    "sticks_per_carton": 200,
                },
                "total_sticks": 20,
                "equivalent_cartons": Decimal("0.1"),
            },
        ],
    }


def make_config() -> JianDaoYunConfig:
    return JianDaoYunConfig(
        create_url=CREATE_URL,
        app_id="test-app-id",
        entry_id="test-entry-id",
        api_key=API_KEY,
    )


def test_build_registration_data_only_contains_business_data() -> None:
    data = build_registration_data(export_data_fixture())

    assert data[IDENTIFIER_WIDGET]["value"] == "2026-09-04 12:00—张三—2个品规—220支卷烟"
    rows = data[ITEMS_WIDGET]["value"]
    assert [row[BARCODE_WIDGET]["value"] for row in rows] == [
        "6900000000001",
        "6900000000002",
    ]
    assert rows[0][TYPE_WIDGET]["value"] == "卷烟"
    assert rows[0][QUANTITY_WIDGET]["value"] == 1
    assert rows[1][QUANTITY_WIDGET]["value"] == 0.1
    assert data["_widget_1788244617473"]["value"] == ""
    assert "app_id" not in data
    assert "entry_id" not in data
    assert CREATE_URL not in json.dumps(data, ensure_ascii=False)


def test_registration_data_rejects_empty_items() -> None:
    export_data = export_data_fixture()
    export_data["items"] = []

    with pytest.raises(ValueError, match="品规"):
        build_registration_data(export_data)


def test_payload_sha256_is_stable_for_key_order() -> None:
    first = {"乙": Decimal("0.1"), "甲": {"value": 1}}
    second = {"甲": {"value": 1}, "乙": Decimal("0.1")}

    assert payload_sha256(first) == payload_sha256(second)
    assert len(payload_sha256(first)) == 64


def test_create_registration_adds_envelope_only_when_sending() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"data": {"_id": "external-id", "createTime": "2026-09-04T12:00:01Z"}},
        )

    data = build_registration_data(export_data_fixture())
    result = create_registration(
        make_config(),
        data,
        transport=httpx.MockTransport(handler),
    )

    assert result.data_id == "external-id"
    assert result.created_at == "2026-09-04T12:00:01Z"
    assert len(requests) == 1
    request = requests[0]
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    body = json.loads(request.content)
    assert body == {
        "app_id": "test-app-id",
        "entry_id": "test-entry-id",
        "is_start_workflow": False,
        "is_start_trigger": False,
        "data": data,
    }


@pytest.mark.parametrize("status_code", [400, 401, 403, 422, 499])
def test_create_registration_classifies_4xx_as_rejected(status_code: int) -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code, text=f"rejected {API_KEY}")

    with pytest.raises(ExternalRejectedError, match=f"HTTP {status_code}") as exc_info:
        create_registration(
            make_config(),
            build_registration_data(export_data_fixture()),
            transport=httpx.MockTransport(handler),
        )

    assert attempts == 1
    assert API_KEY not in str(exc_info.value)


@pytest.mark.parametrize(
    ("status_code", "content"),
    [(500, b"server error"), (200, b"not-json"), (200, b'{"data":{}}')],
)
def test_create_registration_classifies_uncertain_responses(
    status_code: int,
    content: bytes,
) -> None:
    attempts = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status_code, content=content)

    with pytest.raises(ExternalUncertainError) as exc_info:
        create_registration(
            make_config(),
            build_registration_data(export_data_fixture()),
            transport=httpx.MockTransport(handler),
        )

    assert attempts == 1
    message = str(exc_info.value)
    assert API_KEY not in message
    assert "Authorization" not in message
    assert "6900000000001" not in message


def test_create_registration_classifies_network_timeout_without_retry() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(ExternalUncertainError, match="ReadTimeout") as exc_info:
        create_registration(
            make_config(),
            build_registration_data(export_data_fixture()),
            transport=httpx.MockTransport(handler),
        )

    assert attempts == 1
    assert API_KEY not in str(exc_info.value)


def test_config_rejects_blank_required_values() -> None:
    with pytest.raises(ValueError, match="配置不完整"):
        JianDaoYunConfig(create_url="", app_id="", entry_id="", api_key="")
