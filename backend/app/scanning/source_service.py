from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.auth import Role
from app.models.finalization import ScanItemSourceAllocation
from app.models.scanning import ScanSession, ScanSessionItem
from app.scanning.regions import source_key, validate_source_location
from app.scanning.scan_service import ScanSessionItemNotFoundError
from app.scanning.service import (
    ScanSessionForbiddenError,
    get_scan_session,
)
from app.schemas.auth import AuthUser


class QuantityNotPackAlignedError(ValueError):
    pass


class SourceQuantityMismatchError(ValueError):
    pass


@dataclass(frozen=True)
class NormalizedAllocation:
    source_type: str
    province_name: str | None
    city_name: str | None
    pack_count: int
    quantity_sticks: int
    equivalent_cartons: Decimal
    source_key: str


def required_pack_count(*, total_sticks: int, sticks_per_pack: int) -> int:
    if sticks_per_pack <= 0 or total_sticks < 0 or total_sticks % sticks_per_pack != 0:
        raise QuantityNotPackAlignedError("卷烟数量必须按整包核对")
    return total_sticks // sticks_per_pack


def normalize_allocations(
    allocations: list[dict[str, object]],
    *,
    sticks_per_pack: int,
    required_sticks: int,
) -> list[NormalizedAllocation]:
    required_pack_count(total_sticks=required_sticks, sticks_per_pack=sticks_per_pack)
    merged: dict[str, NormalizedAllocation] = {}

    for allocation in allocations:
        pack_count = allocation.get("pack_count")
        if isinstance(pack_count, bool) or not isinstance(pack_count, int) or pack_count <= 0:
            raise SourceQuantityMismatchError("来源数量必须填写正整数包数")
        source_type = str(allocation.get("source_type", ""))
        province, city = validate_source_location(
            source_type,
            allocation.get("province_name"),  # type: ignore[arg-type]
            allocation.get("city_name"),  # type: ignore[arg-type]
        )
        key = source_key(source_type, province, city)
        previous = merged.get(key)
        merged_pack_count = pack_count + (previous.pack_count if previous else 0)
        merged[key] = NormalizedAllocation(
            source_type=source_type,
            province_name=province,
            city_name=city,
            pack_count=merged_pack_count,
            quantity_sticks=merged_pack_count * sticks_per_pack,
            equivalent_cartons=Decimal(merged_pack_count) / Decimal(10),
            source_key=key,
        )

    if sum(item.quantity_sticks for item in merged.values()) != required_sticks:
        raise SourceQuantityMismatchError("来源分配数量必须与品规最终数量完全一致")
    return list(merged.values())


def serialize_allocation(model: ScanItemSourceAllocation) -> dict[str, object]:
    return {
        "id": model.id,
        "source_type": model.source_type,
        "source_type_name": {
            "OUTSIDE_PROVINCE": "外省流入",
            "UNKNOWN": "来源不详",
            "LOCAL_HUAINAN": "市内串码",
            "ANHUI_OTHER_CITY": "省内市外",
        }[model.source_type],
        "province_name": model.province_name,
        "city_name": model.city_name,
        "pack_count": model.pack_count,
        "equivalent_cartons": f"{Decimal(model.pack_count) / Decimal(10):.1f}",
        "quantity_sticks": model.quantity_sticks,
    }


def product_source_state(
    session: Session,
    item: ScanSessionItem,
) -> dict[str, object]:
    sticks_per_pack = int(item.product_snapshot["sticks_per_pack"])
    required = required_pack_count(
        total_sticks=item.total_sticks,
        sticks_per_pack=sticks_per_pack,
    )
    allocations = list(
        session.scalars(
            select(ScanItemSourceAllocation)
            .where(ScanItemSourceAllocation.session_item_id == item.id)
            .order_by(ScanItemSourceAllocation.id)
        )
    )
    allocated = sum(allocation.pack_count for allocation in allocations)
    return {
        "product_id": item.product_id,
        "product_snapshot": item.product_snapshot,
        "required_pack_count": required,
        "allocated_pack_count": allocated,
        "remaining_pack_count": required - allocated,
        "allocations": [serialize_allocation(allocation) for allocation in allocations],
    }


def replace_item_allocations_in_transaction(
    session: Session,
    current_user: AuthUser,
    item: ScanSessionItem,
    allocations: list[dict[str, object]],
    *,
    now: datetime,
) -> None:
    sticks_per_pack = int(item.product_snapshot["sticks_per_pack"])
    normalized = normalize_allocations(
        allocations,
        sticks_per_pack=sticks_per_pack,
        required_sticks=item.total_sticks,
    )
    session.execute(
        delete(ScanItemSourceAllocation).where(
            ScanItemSourceAllocation.session_item_id == item.id
        )
    )
    session.add_all(
        [
            ScanItemSourceAllocation(
                session_item_id=item.id,
                source_type=allocation.source_type,
                province_name=allocation.province_name,
                city_name=allocation.city_name,
                pack_count=allocation.pack_count,
                quantity_sticks=allocation.quantity_sticks,
                source_key=allocation.source_key,
                created_by=current_user.id,
                updated_by=current_user.id,
                created_at=now,
                updated_at=now,
            )
            for allocation in normalized
        ]
    )


def list_source_allocations(
    session: Session,
    current_user: AuthUser,
    session_id: int,
) -> list[dict[str, object]]:
    get_scan_session(session, current_user, session_id)
    items = list(
        session.scalars(
            select(ScanSessionItem)
            .where(ScanSessionItem.session_id == session_id)
            .order_by(ScanSessionItem.id)
        )
    )
    return [product_source_state(session, item) for item in items]


def replace_source_allocations(
    session: Session,
    current_user: AuthUser,
    session_id: int,
    product_id: int,
    allocations: list[dict[str, object]],
) -> dict[str, object]:
    if current_user.role == Role.VIEWER:
        raise ScanSessionForbiddenError("当前账号不能编辑卷烟来源")
    get_scan_session(session, current_user, session_id)
    batch = session.scalar(
        select(ScanSession).where(ScanSession.id == session_id).with_for_update()
    )
    if batch is None:
        raise ScanSessionItemNotFoundError("扫描批次不存在")
    item = session.scalar(
        select(ScanSessionItem)
        .where(
            ScanSessionItem.session_id == session_id,
            ScanSessionItem.product_id == product_id,
        )
        .with_for_update()
    )
    if item is None:
        raise ScanSessionItemNotFoundError("当前批次不存在该品规汇总项")

    current_time = datetime.now(UTC).replace(tzinfo=None)
    replace_item_allocations_in_transaction(
        session,
        current_user,
        item,
        allocations,
        now=current_time,
    )
    session.commit()
    refreshed_item = session.scalar(
        select(ScanSessionItem).where(ScanSessionItem.id == item.id)
    )
    if refreshed_item is None:
        raise ScanSessionItemNotFoundError("当前批次不存在该品规汇总项")
    return product_source_state(session, refreshed_item)
