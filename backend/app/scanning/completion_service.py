from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session, aliased

from app.models.auth import Role
from app.models.finalization import ScanItemSourceAllocation
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem
from app.scanning.scan_service import get_scan_state
from app.scanning.service import ScanSessionForbiddenError, get_scan_session
from app.scanning.source_service import required_pack_count
from app.schemas.auth import AuthUser


class SourceAllocationRequiredError(ValueError):
    pass


class ExceptionConfirmationRequiredError(ValueError):
    pass


class FinalizationEmptyError(ValueError):
    pass


@dataclass(frozen=True)
class CompletionResult:
    scan_session: ScanSession
    summary: dict[str, int]
    source_product_count: int
    source_allocated_product_count: int
    unknown_count: int
    unresolved_ambiguity_count: int


def exception_counts(session: Session, session_id: int) -> tuple[int, int]:
    unknown_count = session.scalar(
        select(func.count(ScanEvent.id)).where(
            ScanEvent.session_id == session_id,
            ScanEvent.result == "UNKNOWN",
        )
    ) or 0
    resolution = aliased(ScanEvent)
    resolved = exists(
        select(resolution.id).where(resolution.source_event_id == ScanEvent.id)
    )
    unresolved_count = session.scalar(
        select(func.count(ScanEvent.id)).where(
            ScanEvent.session_id == session_id,
            ScanEvent.result == "AMBIGUOUS",
            ~resolved,
        )
    ) or 0
    return int(unknown_count), int(unresolved_count)


def source_completion_counts(
    session: Session,
    items: list[ScanSessionItem],
) -> tuple[int, int]:
    valid_items = [item for item in items if item.total_sticks > 0]
    if not valid_items:
        raise FinalizationEmptyError("批次没有可完成的有效卷烟品规")

    allocated_count = 0
    for item in valid_items:
        sticks_per_pack = int(item.product_snapshot["sticks_per_pack"])
        required_pack_count(
            total_sticks=item.total_sticks,
            sticks_per_pack=sticks_per_pack,
        )
        allocated_sticks = session.scalar(
            select(func.coalesce(func.sum(ScanItemSourceAllocation.quantity_sticks), 0)).where(
                ScanItemSourceAllocation.session_item_id == item.id
            )
        ) or 0
        if int(allocated_sticks) != item.total_sticks:
            raise SourceAllocationRequiredError(
                f"品规“{item.product_snapshot['standard_name']}”的来源分配尚未完成"
            )
        allocated_count += 1
    return len(valid_items), allocated_count


def complete_scan_session(
    session: Session,
    current_user: AuthUser,
    session_id: int,
    *,
    confirm_exceptions: bool,
    now: datetime | None = None,
) -> CompletionResult:
    if current_user.role == Role.VIEWER:
        raise ScanSessionForbiddenError("当前账号不能完成扫描批次")
    get_scan_session(session, current_user, session_id)
    try:
        batch = session.scalar(
            select(ScanSession).where(ScanSession.id == session_id).with_for_update()
        )
        if batch is None:
            raise FinalizationEmptyError("扫描批次不存在")
        items = list(
            session.scalars(
                select(ScanSessionItem)
                .where(ScanSessionItem.session_id == session_id)
                .order_by(ScanSessionItem.id)
                .with_for_update()
            )
        )
        source_product_count, allocated_count = source_completion_counts(session, items)
        unknown_count, unresolved_count = exception_counts(session, session_id)
        if (unknown_count > 0 or unresolved_count > 0) and not confirm_exceptions:
            raise ExceptionConfirmationRequiredError(
                "批次存在异常编码，请确认后再完成"
            )

        if batch.status == "DRAFT":
            current_time = now or datetime.now(UTC).replace(tzinfo=None)
            batch.status = "COMPLETED"
            batch.completed_at = current_time
            batch.updated_at = current_time
            session.commit()
        else:
            session.commit()

        state = get_scan_state(session, current_user, session_id)
        return CompletionResult(
            scan_session=batch,
            summary=state["summary"],
            source_product_count=source_product_count,
            source_allocated_product_count=allocated_count,
            unknown_count=unknown_count,
            unresolved_ambiguity_count=unresolved_count,
        )
    except Exception:
        session.rollback()
        raise
