import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.branches import BRANCH_NAMES
from app.models.auth import Role, User
from app.models.scanning import ScanSession, ScanSessionItem
from app.schemas.auth import AuthUser

BUSINESS_TYPE_NAMES = {
    "MARKET_INSPECTION": "市场检查",
    "DELIVERY_CHANNEL": "寄递渠道",
    "SPECIAL_TRANSPORT": "专车运输",
    "OTHER": "其他",
}
STATUS_NAMES = {"DRAFT": "进行中", "COMPLETED": "已完成"}
CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")


class BusinessTypeInvalidError(ValueError):
    pass


class BranchRequiredError(ValueError):
    pass


class BranchInvalidError(ValueError):
    pass


class ScanSessionForbiddenError(ValueError):
    pass


class ScanSessionNotFoundError(ValueError):
    pass


class ScanSessionCreateFailedError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScanSessionListResult:
    items: list[ScanSession]
    total: int


def china_datetime(value: datetime) -> datetime:
    utc_value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return utc_value.astimezone(CHINA_TIMEZONE)


def generate_session_no(*, now: datetime, suffix: int) -> str:
    return f"PD{china_datetime(now):%Y%m%d-%H%M%S}-{suffix:04d}"


def business_type_name(value: str) -> str:
    try:
        return BUSINESS_TYPE_NAMES[value]
    except KeyError as exc:
        raise BusinessTypeInvalidError("业务类型无效") from exc


def status_name(value: str) -> str:
    return STATUS_NAMES.get(value, value)


def build_display_label(
    *,
    created_at: datetime,
    operator_name: str,
    product_count: int,
    total_sticks: int,
) -> str:
    display_time = china_datetime(created_at)
    return (
        f"{display_time:%Y-%m-%d %H:%M}—{operator_name}—{product_count}个品规—{total_sticks}支卷烟"
    )


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def creation_branch(current_user: AuthUser, requested_branch: object) -> str:
    if current_user.role == Role.VIEWER:
        raise ScanSessionForbiddenError("当前账号不能新建扫描批次")
    if current_user.role == Role.OPERATOR:
        if current_user.branch_code not in BRANCH_NAMES:
            raise BranchInvalidError("当前账号所属分局无效")
        return current_user.branch_code
    branch_code = optional_text(requested_branch)
    if branch_code is None:
        raise BranchRequiredError("请选择所属分局")
    if branch_code not in BRANCH_NAMES:
        raise BranchInvalidError("所属分局无效")
    return branch_code


def create_scan_session(
    session: Session,
    current_user: AuthUser,
    payload: dict[str, object],
    *,
    now: datetime | None = None,
    suffix_factory: Callable[[], int] | None = None,
) -> ScanSession:
    business_type = str(payload.get("business_type", ""))
    business_type_name(business_type)
    branch_code = creation_branch(current_user, payload.get("branch_code"))
    current_time = now or datetime.now(UTC).replace(tzinfo=None)
    next_suffix = suffix_factory or (lambda: secrets.randbelow(10_000))

    for _ in range(3):
        model = ScanSession(
            session_no=generate_session_no(now=current_time, suffix=next_suffix()),
            business_type=business_type,
            filing_case_no=optional_text(payload.get("filing_case_no")),
            location=optional_text(payload.get("location")),
            notes=optional_text(payload.get("notes")),
            branch_code=branch_code,
            operator_id=current_user.id,
            status="DRAFT",
            completed_at=None,
            created_at=current_time,
            updated_at=current_time,
        )
        session.add(model)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            continue
        session.refresh(model)
        return model
    raise ScanSessionCreateFailedError("批次创建失败，请重试")


def data_scope_filter(current_user: AuthUser):
    if current_user.role == Role.ADMIN:
        return None
    if current_user.branch_code not in BRANCH_NAMES:
        return ScanSession.branch_code == "__NO_BRANCH__"
    non_admin_operator_ids = select(User.id).where(User.role != Role.ADMIN)
    return and_(
        ScanSession.branch_code == current_user.branch_code,
        ScanSession.operator_id.in_(non_admin_operator_ids),
    )


def list_scan_sessions(
    session: Session,
    current_user: AuthUser,
    filters: dict[str, object],
    page: int,
    page_size: int,
) -> ScanSessionListResult:
    conditions = []
    scope = data_scope_filter(current_user)
    if scope is not None:
        conditions.append(scope)
    query = optional_text(filters.get("query"))
    if query:
        pattern = f"%{query}%"
        conditions.append(
            or_(
                ScanSession.session_no.like(pattern),
                ScanSession.filing_case_no.like(pattern),
                ScanSession.location.like(pattern),
            )
        )
    business_type = optional_text(filters.get("business_type"))
    if business_type:
        business_type_name(business_type)
        conditions.append(ScanSession.business_type == business_type)
    status = optional_text(filters.get("status"))
    if status:
        conditions.append(ScanSession.status == status)
    requested_branch = optional_text(filters.get("branch_code"))
    if current_user.role == Role.ADMIN and requested_branch:
        if requested_branch not in BRANCH_NAMES:
            raise BranchInvalidError("所属分局无效")
        conditions.append(ScanSession.branch_code == requested_branch)

    total = session.scalar(select(func.count(ScanSession.id)).where(*conditions)) or 0
    items = list(
        session.scalars(
            select(ScanSession)
            .where(*conditions)
            .order_by(ScanSession.created_at.desc(), ScanSession.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return ScanSessionListResult(items=items, total=total)


def get_scan_session(
    session: Session,
    current_user: AuthUser,
    session_id: int,
) -> ScanSession:
    conditions = [ScanSession.id == session_id]
    scope = data_scope_filter(current_user)
    if scope is not None:
        conditions.append(scope)
    model = session.scalar(select(ScanSession).where(*conditions))
    if model is None:
        raise ScanSessionNotFoundError("扫描批次不存在")
    return model


def serialize_scan_session(session: Session, model: ScanSession) -> dict[str, object]:
    operator_name = session.scalar(select(User.display_name).where(User.id == model.operator_id))
    resolved_operator_name = operator_name or "未知人员"
    product_count, total_sticks = session.execute(
        select(
            func.count(ScanSessionItem.id),
            func.coalesce(func.sum(ScanSessionItem.total_sticks), 0),
        ).where(ScanSessionItem.session_id == model.id)
    ).one()
    return {
        "id": model.id,
        "session_no": model.session_no,
        "business_type": model.business_type,
        "business_type_name": business_type_name(model.business_type),
        "filing_case_no": model.filing_case_no,
        "location": model.location,
        "notes": model.notes,
        "branch_code": model.branch_code,
        "branch_name": BRANCH_NAMES[model.branch_code],
        "operator_id": model.operator_id,
        "operator_name": resolved_operator_name,
        "status": model.status,
        "status_name": status_name(model.status),
        "completed_at": model.completed_at,
        "product_count": product_count,
        "total_sticks": total_sticks,
        "display_label": build_display_label(
            created_at=model.created_at,
            operator_name=resolved_operator_name,
            product_count=product_count,
            total_sticks=total_sticks,
        ),
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }
