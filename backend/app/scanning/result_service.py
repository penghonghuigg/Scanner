import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import Role
from app.models.catalog import CigaretteProduct
from app.models.finalization import ScanItemSourceAllocation
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem
from app.scanning.scan_service import (
    IdempotencyConflictError,
    ScanSessionItemNotFoundError,
    product_snapshot,
)
from app.scanning.service import (
    ScanSessionForbiddenError,
    ScanSessionNotFoundError,
    data_scope_filter,
)
from app.scanning.source_service import (
    normalize_allocations,
    product_source_state,
    replace_item_allocations_in_transaction,
)
from app.schemas.auth import AuthUser


class ResultSessionNotCompletedError(ValueError):
    pass


class ResultProductNotFoundError(ValueError):
    pass


class ProductInactiveError(ValueError):
    pass


@dataclass(frozen=True)
class ResultItemOperation:
    item: ScanSessionItem
    source_state: dict[str, object]
    event: ScanEvent
    idempotent_replay: bool


def locked_completed_session(
    session: Session,
    current_user: AuthUser,
    session_id: int,
) -> ScanSession:
    if current_user.role == Role.VIEWER:
        raise ScanSessionForbiddenError("当前账号不能修订盘点结果")
    conditions = [ScanSession.id == session_id]
    scope = data_scope_filter(current_user)
    if scope is not None:
        conditions.append(scope)
    batch = session.scalar(select(ScanSession).where(*conditions).with_for_update())
    if batch is None:
        raise ScanSessionNotFoundError("盘点结果不存在")
    if batch.status != "COMPLETED":
        raise ResultSessionNotCompletedError("只能修订已完成的盘点结果")
    return batch


def quantity_sticks(snapshot: dict[str, object], quantity_cartons: Decimal) -> int:
    sticks_per_carton = int(snapshot["sticks_per_carton"])
    if sticks_per_carton % 10 != 0:
        raise ValueError("当前品规无法按 0.1 条精确换算支数")
    return int(quantity_cartons * 10) * (sticks_per_carton // 10)


def normalized_allocation_dicts(
    allocations: list[dict[str, object]],
    *,
    snapshot: dict[str, object],
    required_sticks: int,
) -> list[dict[str, object]]:
    normalized = normalize_allocations(
        allocations,
        sticks_per_pack=int(snapshot["sticks_per_pack"]),
        required_sticks=required_sticks,
    )
    return [
        {
            "source_type": item.source_type,
            "province_name": item.province_name,
            "city_name": item.city_name,
            "pack_count": item.pack_count,
        }
        for item in sorted(normalized, key=lambda item: item.source_key)
    ]


def request_reason(
    operation: str,
    product_id: int,
    quantity_cartons: Decimal,
    allocations: list[dict[str, object]],
) -> str:
    canonical = json.dumps(
        {
            "operation": operation,
            "product_id": product_id,
            "quantity_cartons": f"{quantity_cartons:.1f}",
            "source_allocations": allocations,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    action = "加入" if operation == "ADD" else "设为"
    return (
        f"已完成结果修订：{action} {quantity_cartons:.1f} 条；"
        f"请求摘要：{fingerprint}"
    )


def existing_operation(
    session: Session,
    *,
    request_id: str,
    session_id: int,
    product_id: int,
    reason: str,
) -> ScanEvent | None:
    event = session.scalar(select(ScanEvent).where(ScanEvent.request_id == request_id))
    if event is None:
        return None
    if (
        event.session_id != session_id
        or event.event_type != "ADJUST"
        or event.product_id != product_id
        or event.reason != reason
    ):
        raise IdempotencyConflictError("请求号已用于其他结果修订内容")
    return event


def current_allocation_inputs(
    session: Session,
    item_id: int,
) -> list[dict[str, object]]:
    models = list(
        session.scalars(
            select(ScanItemSourceAllocation)
            .where(ScanItemSourceAllocation.session_item_id == item_id)
            .order_by(ScanItemSourceAllocation.id)
            .with_for_update()
        )
    )
    return [
        {
            "source_type": model.source_type,
            "province_name": model.province_name,
            "city_name": model.city_name,
            "pack_count": model.pack_count,
        }
        for model in models
    ]


def add_result_item(
    session: Session,
    current_user: AuthUser,
    session_id: int,
    *,
    request_id: str,
    product_id: int,
    quantity_cartons: Decimal,
    allocations: list[dict[str, object]],
    now: datetime | None = None,
) -> ResultItemOperation:
    current_time = now or datetime.now(UTC).replace(tzinfo=None)
    try:
        batch = locked_completed_session(session, current_user, session_id)
        product = session.scalar(
            select(CigaretteProduct)
            .where(CigaretteProduct.id == product_id)
            .with_for_update()
        )
        if product is None:
            raise ResultProductNotFoundError("卷烟品规不存在")
        if not product.is_active:
            raise ProductInactiveError("已停用品规不能加入盘点结果")
        item = session.scalar(
            select(ScanSessionItem)
            .where(
                ScanSessionItem.session_id == session_id,
                ScanSessionItem.product_id == product_id,
            )
            .with_for_update()
        )
        snapshot = dict(item.product_snapshot) if item else product_snapshot(product)
        added_sticks = quantity_sticks(snapshot, quantity_cartons)
        added_allocations = normalized_allocation_dicts(
            allocations,
            snapshot=snapshot,
            required_sticks=added_sticks,
        )
        reason = request_reason("ADD", product_id, quantity_cartons, added_allocations)
        replay = existing_operation(
            session,
            request_id=request_id,
            session_id=session_id,
            product_id=product_id,
            reason=reason,
        )
        if replay is not None:
            if item is None:
                raise ScanSessionItemNotFoundError("结果中的卷烟品规不存在")
            session.commit()
            return ResultItemOperation(
                item=item,
                source_state=product_source_state(session, item),
                event=replay,
                idempotent_replay=True,
            )

        existing_allocations = current_allocation_inputs(session, item.id) if item else []
        if item is None:
            item = ScanSessionItem(
                session_id=session_id,
                product_id=product_id,
                carton_count=0,
                pack_count=0,
                manual_delta_sticks=0,
                total_sticks=0,
                product_snapshot=snapshot,
                updated_at=current_time,
            )
            session.add(item)
            session.flush()
        item.manual_delta_sticks += added_sticks
        item.total_sticks += added_sticks
        item.updated_at = current_time
        combined_allocations = existing_allocations + added_allocations
        replace_item_allocations_in_transaction(
            session,
            current_user,
            item,
            combined_allocations,
            now=current_time,
        )
        event = ScanEvent(
            request_id=request_id,
            session_id=session_id,
            event_type="ADJUST",
            result="SUCCESS",
            raw_code=str(snapshot["carton_code"]),
            product_id=product_id,
            unit_type="STICK",
            delta_sticks=added_sticks,
            source_event_id=None,
            reason=reason,
            candidate_snapshot=None,
            product_snapshot=snapshot,
            operator_id=current_user.id,
            created_at=current_time,
        )
        session.add(event)
        batch.updated_at = current_time
        session.commit()
        session.refresh(item)
        session.refresh(event)
        return ResultItemOperation(
            item=item,
            source_state=product_source_state(session, item),
            event=event,
            idempotent_replay=False,
        )
    except Exception:
        session.rollback()
        raise


def replace_result_item(
    session: Session,
    current_user: AuthUser,
    session_id: int,
    product_id: int,
    *,
    request_id: str,
    quantity_cartons: Decimal,
    allocations: list[dict[str, object]],
    now: datetime | None = None,
) -> ResultItemOperation:
    current_time = now or datetime.now(UTC).replace(tzinfo=None)
    try:
        batch = locked_completed_session(session, current_user, session_id)
        item = session.scalar(
            select(ScanSessionItem)
            .where(
                ScanSessionItem.session_id == session_id,
                ScanSessionItem.product_id == product_id,
            )
            .with_for_update()
        )
        if item is None:
            raise ScanSessionItemNotFoundError("结果中的卷烟品规不存在")
        snapshot = dict(item.product_snapshot)
        target_sticks = quantity_sticks(snapshot, quantity_cartons)
        normalized_allocations = normalized_allocation_dicts(
            allocations,
            snapshot=snapshot,
            required_sticks=target_sticks,
        )
        reason = request_reason(
            "REPLACE",
            product_id,
            quantity_cartons,
            normalized_allocations,
        )
        replay = existing_operation(
            session,
            request_id=request_id,
            session_id=session_id,
            product_id=product_id,
            reason=reason,
        )
        if replay is not None:
            session.commit()
            return ResultItemOperation(
                item=item,
                source_state=product_source_state(session, item),
                event=replay,
                idempotent_replay=True,
            )

        scanned_sticks = (
            item.carton_count * int(snapshot["sticks_per_carton"])
            + item.pack_count * int(snapshot["sticks_per_pack"])
        )
        delta_sticks = target_sticks - item.total_sticks
        item.manual_delta_sticks = target_sticks - scanned_sticks
        item.total_sticks = target_sticks
        item.updated_at = current_time
        replace_item_allocations_in_transaction(
            session,
            current_user,
            item,
            normalized_allocations,
            now=current_time,
        )
        event = ScanEvent(
            request_id=request_id,
            session_id=session_id,
            event_type="ADJUST",
            result="SUCCESS",
            raw_code=str(snapshot["carton_code"]),
            product_id=product_id,
            unit_type="STICK",
            delta_sticks=delta_sticks,
            source_event_id=None,
            reason=reason,
            candidate_snapshot=None,
            product_snapshot=snapshot,
            operator_id=current_user.id,
            created_at=current_time,
        )
        session.add(event)
        batch.updated_at = current_time
        session.commit()
        session.refresh(item)
        session.refresh(event)
        return ResultItemOperation(
            item=item,
            source_state=product_source_state(session, item),
            event=event,
            idempotent_replay=False,
        )
    except Exception:
        session.rollback()
        raise
