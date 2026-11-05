from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

IDENTIFIER_WIDGET = "_widget_1788244617469"
BRANCH_WIDGET = "_widget_1788244617474"
FILING_CASE_WIDGET = "_widget_1788244617473"
OPERATOR_WIDGET = "_widget_1788244617475"
ITEMS_WIDGET = "_widget_1788244617471"

BARCODE_WIDGET = "_widget_1788247452462"
PRODUCT_NAME_WIDGET = "_widget_1788245720805"
BRAND_WIDGET = "_widget_1788247452464"
TYPE_WIDGET = "_widget_1788247452463"
STICKS_PER_CARTON_WIDGET = "_widget_1788247452467"
QUANTITY_WIDGET = "_widget_1788247452468"


class ExternalRejectedError(RuntimeError):
    """外部系统明确拒绝请求，可以由操作员再次尝试。"""


class ExternalUncertainError(RuntimeError):
    """外部调用结果不确定，禁止自动或人工直接重试。"""


@dataclass(frozen=True)
class JianDaoYunConfig:
    create_url: str
    app_id: str
    entry_id: str
    api_key: str

    def __post_init__(self) -> None:
        values = {
            "create_url": self.create_url.strip(),
            "app_id": self.app_id.strip(),
            "entry_id": self.entry_id.strip(),
            "api_key": self.api_key.strip(),
        }
        if not all(values.values()):
            raise ValueError("简道云配置不完整")
        for name, value in values.items():
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class JianDaoYunCreateResult:
    data_id: str
    created_at: str | None


def _json_number(value: Decimal) -> int | float:
    if not value.is_finite():
        raise ValueError("简道云数值必须是有限小数")
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def _json_compatible(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _json_number(value)
    if isinstance(value, Mapping):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return value


def _required_mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} 数据格式不正确")
    return value


def build_registration_data(export_data: Mapping[str, object]) -> dict[str, object]:
    session = _required_mapping(export_data.get("session"), "批次")
    raw_items = export_data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("批次没有可导入的卷烟品规")

    rows: list[dict[str, object]] = []
    for raw_item in raw_items:
        item = _required_mapping(raw_item, "品规")
        product = _required_mapping(item.get("product_snapshot"), "品规快照")
        total_sticks = Decimal(str(item["total_sticks"]))
        sticks_per_carton = int(product["sticks_per_carton"])
        if total_sticks <= 0 or sticks_per_carton <= 0:
            raise ValueError("品规数量和条支比必须大于零")
        rows.append(
            {
                BARCODE_WIDGET: {"value": str(product["carton_code"])},
                PRODUCT_NAME_WIDGET: {"value": str(product["standard_name"])},
                BRAND_WIDGET: {"value": str(product["brand"])},
                TYPE_WIDGET: {"value": "卷烟"},
                STICKS_PER_CARTON_WIDGET: {"value": sticks_per_carton},
                QUANTITY_WIDGET: {
                    "value": _json_number(total_sticks / Decimal(sticks_per_carton))
                },
            }
        )

    return {
        IDENTIFIER_WIDGET: {"value": str(session["display_label"])},
        BRANCH_WIDGET: {"value": str(session["branch_name"])},
        FILING_CASE_WIDGET: {"value": str(session.get("filing_case_no") or "")},
        OPERATOR_WIDGET: {"value": str(session["operator_name"])},
        ITEMS_WIDGET: {"value": rows},
    }


def canonical_json(data: Mapping[str, object]) -> str:
    return json.dumps(
        _json_compatible(data),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_sha256(data: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def create_registration(
    config: JianDaoYunConfig,
    data: Mapping[str, object],
    *,
    transport: httpx.BaseTransport | None = None,
) -> JianDaoYunCreateResult:
    payload = {
        "app_id": config.app_id,
        "entry_id": config.entry_id,
        "is_start_workflow": False,
        "is_start_trigger": False,
        "data": _json_compatible(data),
    }
    try:
        with httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(20.0, connect=5.0),
        ) as client:
            response = client.post(
                config.create_url,
                headers={"Authorization": f"Bearer {config.api_key}"},
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise ExternalUncertainError(f"访问简道云失败：{type(exc).__name__}") from None

    if 400 <= response.status_code < 500:
        raise ExternalRejectedError(f"简道云明确拒绝请求：HTTP {response.status_code}")
    if not response.is_success:
        raise ExternalUncertainError(f"简道云响应状态不确定：HTTP {response.status_code}")

    try:
        response_body = response.json()
    except ValueError:
        raise ExternalUncertainError("简道云成功响应不是合法 JSON") from None
    response_data = response_body.get("data") if isinstance(response_body, dict) else None
    data_id = response_data.get("_id") if isinstance(response_data, dict) else None
    if not isinstance(data_id, str) or not data_id.strip():
        raise ExternalUncertainError("简道云成功响应缺少 data._id")

    created_at = response_data.get("createTime")
    return JianDaoYunCreateResult(
        data_id=data_id.strip(),
        created_at=str(created_at) if created_at is not None else None,
    )
