import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import Role, User
from app.models.catalog import CigaretteProduct
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem
from app.scanning.service import (
    ScanSessionForbiddenError,
    ScanSessionNotFoundError,
    data_scope_filter,
    get_scan_session,
)
from app.schemas.auth import AuthUser

CODE_PATTERN = re.compile(r"\d{13}")


class BarcodeInvalidError(ValueError):
    pass


class ScanSessionClosedError(ValueError):
    pass


class IdempotencyConflictError(ValueError):
    pass


class ScanEventNotFoundError(ValueError):
    pass


class AmbiguityAlreadyResolvedError(ValueError):
    pass


class AmbiguityCandidateInvalidError(ValueError):
    pass


@dataclass(frozen=True)
class ScanOperationResult:
    event: ScanEvent
    idempotent_replay: bool


def normalize_scan_code(value: str) -> str:
    normalized = value.strip()
    if not CODE_PATTERN.fullmatch(normalized):
        raise BarcodeInvalidError("编码必须为 13 位数字")
    return normalized


def decimal_text(value: Decimal | None) -> str | None:
    return f"{value:.2f}" if value is not None else None


def product_snapshot(product: CigaretteProduct) -> dict[str, object]:
    return {
        "product_id": product.id,
        "carton_code": product.carton_code,
        "pack_code": product.pack_code,
        "brand": product.brand,
        "standard_name": product.standard_name,
        "carton_retail_price": decimal_text(product.carton_retail_price),
        "sticks_per_pack": product.sticks_per_pack,
        "packs_per_carton": product.packs_per_carton,
        "sticks_per_carton": product.sticks_per_pack * product.packs_per_carton,
    }


def locked_writable_session(
    session: Session,
    current_user: AuthUser,
    session_id: int,
) -> ScanSession:
    if current_user.role == Role.VIEWER:
        raise ScanSessionForbiddenError("当前账号不能录入卷烟")
    conditions = [ScanSession.id == session_id]
    scope = data_scope_filter(current_user)
    if scope is not None:
        conditions.append(scope)
    model = session.scalar(select(ScanSession).where(*conditions).with_for_update())
    if model is None:
        raise ScanSessionNotFoundError("扫描批次不存在")
    if model.status != "DRAFT":
        raise ScanSessionClosedError("批次已完成，不能继续扫码")
    return model


def existing_scan_request(
    session: Session,
    *,
    request_id: str,
    session_id: int,
    raw_code: str,
) -> ScanEvent | None:
    event = session.scalar(select(ScanEvent).where(ScanEvent.request_id == request_id))
    if event is None:
        return None
    if event.session_id != session_id or event.event_type != "SCAN" or event.raw_code != raw_code:
        raise IdempotencyConflictError("请求号已用于其他扫码内容")
    return event


def active_code_matches(
    session: Session,
    code: str,
) -> tuple[str | None, list[CigaretteProduct]]:
    carton = session.scalar(
        select(CigaretteProduct).where(
            CigaretteProduct.carton_code == code,
            CigaretteProduct.is_active.is_(True),
        )
    )
    if carton is not None:
        return "CARTON", [carton]
    packs = list(
        session.scalars(
            select(CigaretteProduct)
            .where(
                CigaretteProduct.pack_code == code,
                CigaretteProduct.is_active.is_(True),
            )
            .order_by(CigaretteProduct.id)
        )
    )
    return ("PACK", packs) if packs else (None, [])


def increment_item(
    session: Session,
    *,
    session_id: int,
    product_id: int,
    unit_type: str,
    snapshot: dict[str, object],
    now: datetime,
) -> int:
    item = session.scalar(
        select(ScanSessionItem)
        .where(
            ScanSessionItem.session_id == session_id,
            ScanSessionItem.product_id == product_id,
        )
        .with_for_update()
    )
    if item is None:
        item = ScanSessionItem(
            session_id=session_id,
            product_id=product_id,
            carton_count=0,
            pack_count=0,
            manual_delta_sticks=0,
            total_sticks=0,
            product_snapshot=snapshot,
            updated_at=now,
        )
        session.add(item)
    if unit_type == "CARTON":
        delta_sticks = int(snapshot["sticks_per_pack"]) * int(snapshot["packs_per_carton"])
        item.carton_count += 1
    else:
        delta_sticks = int(snapshot["sticks_per_pack"])
        item.pack_count += 1
    item.total_sticks += delta_sticks
    item.updated_at = now
    return delta_sticks


def scan_code(
    session: Session,
    current_user: AuthUser,
    session_id: int,
    request_id: str,
    code: str,
    *,
    now: datetime | None = None,
) -> ScanOperationResult:
    normalized_code = normalize_scan_code(code)
    current_time = now or datetime.now(UTC).replace(tzinfo=None)
    try:
        batch = locked_writable_session(session, current_user, session_id)
        existing = existing_scan_request(
            session,
            request_id=request_id,
            session_id=session_id,
            raw_code=normalized_code,
        )
        if existing is not None:
            session.commit()
            return ScanOperationResult(event=existing, idempotent_replay=True)

        unit_type, matches = active_code_matches(session, normalized_code)
        result = "UNKNOWN"
        product: CigaretteProduct | None = None
        snapshot: dict[str, object] | None = None
        candidates: list[dict[str, object]] | None = None
        delta_sticks = 0
        if len(matches) == 1:
            result = "SUCCESS"
            product = matches[0]
            snapshot = product_snapshot(product)
            assert unit_type is not None
            delta_sticks = increment_item(
                session,
                session_id=session_id,
                product_id=product.id,
                unit_type=unit_type,
                snapshot=snapshot,
                now=current_time,
            )
        elif len(matches) > 1:
            result = "AMBIGUOUS"
            candidates = [product_snapshot(candidate) for candidate in matches]

        event = ScanEvent(
            request_id=request_id,
            session_id=session_id,
            event_type="SCAN",
            result=result,
            raw_code=normalized_code,
            product_id=product.id if product is not None else None,
            unit_type=unit_type if result == "SUCCESS" else None,
            delta_sticks=delta_sticks,
            source_event_id=None,
            reason=None,
            candidate_snapshot=candidates,
            product_snapshot=snapshot,
            operator_id=current_user.id,
            created_at=current_time,
        )
        session.add(event)
        batch.updated_at = current_time
        session.commit()
        session.refresh(event)
        return ScanOperationResult(event=event, idempotent_replay=False)
    except Exception:
        session.rollback()
        raise


def existing_resolve_request(
    session: Session,
    *,
    request_id: str,
    session_id: int,
    source_event_id: int,
    product_id: int,
) -> ScanEvent | None:
    event = session.scalar(select(ScanEvent).where(ScanEvent.request_id == request_id))
    if event is None:
        return None
    if (
        event.session_id != session_id
        or event.event_type != "RESOLVE"
        or event.source_event_id != source_event_id
        or event.product_id != product_id
    ):
        raise IdempotencyConflictError("请求号已用于其他歧义处理内容")
    return event


def resolve_ambiguity(
    session: Session,
    current_user: AuthUser,
    session_id: int,
    request_id: str,
    source_event_id: int,
    product_id: int,
    *,
    now: datetime | None = None,
) -> ScanOperationResult:
    current_time = now or datetime.now(UTC).replace(tzinfo=None)
    try:
        batch = locked_writable_session(session, current_user, session_id)
        existing_request = existing_resolve_request(
            session,
            request_id=request_id,
            session_id=session_id,
            source_event_id=source_event_id,
            product_id=product_id,
        )
        if existing_request is not None:
            session.commit()
            return ScanOperationResult(
                event=existing_request,
                idempotent_replay=True,
            )

        source_event = session.scalar(
            select(ScanEvent)
            .where(
                ScanEvent.id == source_event_id,
                ScanEvent.session_id == session_id,
                ScanEvent.event_type == "SCAN",
                ScanEvent.result == "AMBIGUOUS",
            )
            .with_for_update()
        )
        if source_event is None:
            raise ScanEventNotFoundError("歧义扫码事件不存在")
        if (
            session.scalar(
                select(ScanEvent.id).where(
                    ScanEvent.source_event_id == source_event_id,
                    ScanEvent.event_type == "RESOLVE",
                )
            )
            is not None
        ):
            raise AmbiguityAlreadyResolvedError("该歧义编码已经处理")

        candidate = next(
            (
                snapshot
                for snapshot in source_event.candidate_snapshot or []
                if int(snapshot["product_id"]) == product_id
            ),
            None,
        )
        if candidate is None:
            raise AmbiguityCandidateInvalidError("所选品规不属于该歧义编码候选")

        delta_sticks = increment_item(
            session,
            session_id=session_id,
            product_id=product_id,
            unit_type="PACK",
            snapshot=candidate,
            now=current_time,
        )
        event = ScanEvent(
            request_id=request_id,
            session_id=session_id,
            event_type="RESOLVE",
            result="SUCCESS",
            raw_code=source_event.raw_code,
            product_id=product_id,
            unit_type="PACK",
            delta_sticks=delta_sticks,
            source_event_id=source_event_id,
            reason=None,
            candidate_snapshot=None,
            product_snapshot=candidate,
            operator_id=current_user.id,
            created_at=current_time,
        )
        session.add(event)
        batch.updated_at = current_time
        session.commit()
        session.refresh(event)
        return ScanOperationResult(event=event, idempotent_replay=False)
    except Exception:
        session.rollback()
        raise


def serialize_item(item: ScanSessionItem) -> dict[str, object]:
    return {
        "id": item.id,
        "product_id": item.product_id,
        "carton_count": item.carton_count,
        "pack_count": item.pack_count,
        "manual_delta_sticks": item.manual_delta_sticks,
        "total_sticks": item.total_sticks,
        "product_snapshot": item.product_snapshot,
        "updated_at": item.updated_at,
    }


def serialize_event(
    event: ScanEvent,
    *,
    operator_names: dict[int, str],
    resolved_source_ids: set[int],
) -> dict[str, object]:
    return {
        "id": event.id,
        "request_id": event.request_id,
        "event_type": event.event_type,
        "result": event.result,
        "raw_code": event.raw_code,
        "product_id": event.product_id,
        "unit_type": event.unit_type,
        "delta_sticks": event.delta_sticks,
        "source_event_id": event.source_event_id,
        "candidate_snapshot": event.candidate_snapshot,
        "product_snapshot": event.product_snapshot,
        "operator_id": event.operator_id,
        "operator_name": operator_names.get(event.operator_id, "未知人员"),
        "resolved": event.id in resolved_source_ids,
        "created_at": event.created_at,
    }


def serialize_operation_event(
    session: Session,
    event: ScanEvent,
) -> dict[str, object]:
    operator_name = session.scalar(
        select(User.display_name).where(User.id == event.operator_id)
    )
    resolved_source_ids: set[int] = set()
    if event.result == "AMBIGUOUS" and session.scalar(
        select(ScanEvent.id).where(
            ScanEvent.source_event_id == event.id,
            ScanEvent.event_type == "RESOLVE",
        )
    ) is not None:
        resolved_source_ids.add(event.id)
    return serialize_event(
        event,
        operator_names={event.operator_id: operator_name or "未知人员"},
        resolved_source_ids=resolved_source_ids,
    )


def get_scan_state(
    session: Session,
    current_user: AuthUser,
    session_id: int,
) -> dict[str, object]:
    get_scan_session(session, current_user, session_id)
    items = list(
        session.scalars(
            select(ScanSessionItem)
            .where(ScanSessionItem.session_id == session_id)
            .order_by(ScanSessionItem.updated_at.desc(), ScanSessionItem.id.desc())
        )
    )
    resolved_source_ids = set(
        session.scalars(
            select(ScanEvent.source_event_id).where(
                ScanEvent.session_id == session_id,
                ScanEvent.event_type == "RESOLVE",
                ScanEvent.source_event_id.is_not(None),
            )
        )
    )
    recent_events = list(
        session.scalars(
            select(ScanEvent)
            .where(ScanEvent.session_id == session_id)
            .order_by(ScanEvent.created_at.desc(), ScanEvent.id.desc())
            .limit(50)
        )
    )
    pending_ambiguities = list(
        session.scalars(
            select(ScanEvent)
            .where(
                ScanEvent.session_id == session_id,
                ScanEvent.event_type == "SCAN",
                ScanEvent.result == "AMBIGUOUS",
                ScanEvent.id.not_in(resolved_source_ids),
            )
            .order_by(ScanEvent.created_at.desc(), ScanEvent.id.desc())
        )
    )
    event_operator_ids = {event.operator_id for event in [*recent_events, *pending_ambiguities]}
    operator_names = dict(
        session.execute(
            select(User.id, User.display_name).where(User.id.in_(event_operator_ids))
        ).all()
    )
    unknown_count = (
        session.scalar(
            select(func.count(ScanEvent.id)).where(
                ScanEvent.session_id == session_id,
                ScanEvent.result == "UNKNOWN",
            )
        )
        or 0
    )
    summary = {
        "product_count": len(items),
        "carton_count": sum(item.carton_count for item in items),
        "pack_count": sum(item.pack_count for item in items),
        "total_sticks": sum(item.total_sticks for item in items),
        "unknown_count": unknown_count,
        "ambiguous_count": len(pending_ambiguities),
    }
    return {
        "summary": summary,
        "items": [serialize_item(item) for item in items],
        "recent_events": [
            serialize_event(
                event,
                operator_names=operator_names,
                resolved_source_ids=resolved_source_ids,
            )
            for event in recent_events
        ],
        "pending_ambiguities": [
            serialize_event(
                event,
                operator_names=operator_names,
                resolved_source_ids=resolved_source_ids,
            )
            for event in pending_ambiguities
        ],
    }
