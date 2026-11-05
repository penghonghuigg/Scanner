from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.integrations.jiandaoyun import (
    ExternalRejectedError,
    ExternalUncertainError,
    JianDaoYunConfig,
    JianDaoYunCreateResult,
    build_registration_data,
    create_registration,
    payload_sha256,
)
from app.models.auth import Role
from app.models.integration import IntegrationSnapshot
from app.models.scanning import ScanSession
from app.scanning.export_service import build_export_data
from app.scanning.service import ScanSessionForbiddenError, get_scan_session
from app.schemas.auth import AuthUser

PENDING_STALE_AFTER = timedelta(seconds=120)
Sender = Callable[
    [JianDaoYunConfig, Mapping[str, object]],
    JianDaoYunCreateResult,
]


class IntegrationInProgressError(RuntimeError):
    pass


class IntegrationUncertainError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _snapshot_for_update(
    session: Session,
    session_id: int,
) -> IntegrationSnapshot | None:
    return session.scalar(
        select(IntegrationSnapshot)
        .where(IntegrationSnapshot.session_id == session_id)
        .with_for_update()
    )


def _prepare_existing_snapshot(
    session: Session,
    snapshot: IntegrationSnapshot,
    current_user: AuthUser,
    *,
    now: datetime,
) -> IntegrationSnapshot | None:
    if snapshot.status == "SUCCEEDED":
        session.commit()
        return snapshot
    if snapshot.status == "UNCERTAIN":
        session.rollback()
        raise IntegrationUncertainError("该批次导入结果不确定，请人工核查简道云")
    if snapshot.status == "PENDING":
        if now - snapshot.updated_at >= PENDING_STALE_AFTER:
            snapshot.status = "UNCERTAIN"
            snapshot.last_error_code = "PENDING_EXPIRED"
            snapshot.last_error_message = "导入过程异常中断，结果不确定，请人工核查"
            snapshot.updated_at = now
            session.commit()
            raise IntegrationUncertainError("该批次导入过程已超时，请人工核查简道云")
        session.rollback()
        raise IntegrationInProgressError("该批次正在导入简道云")

    snapshot.status = "PENDING"
    snapshot.attempt_count += 1
    snapshot.last_error_code = None
    snapshot.last_error_message = None
    snapshot.last_attempted_by = current_user.id
    snapshot.updated_at = now
    session.commit()
    return None


def _record_external_failure(
    session: Session,
    session_id: int,
    *,
    status: str,
    error_code: str,
    message: str,
    now: datetime,
) -> None:
    snapshot = _snapshot_for_update(session, session_id)
    if snapshot is None:
        session.rollback()
        raise RuntimeError("简道云快照不存在")
    snapshot.status = status
    snapshot.last_error_code = error_code
    snapshot.last_error_message = message[:500]
    snapshot.updated_at = now
    session.commit()


def get_integration_snapshot(
    session: Session,
    current_user: AuthUser,
    session_id: int,
    *,
    now: datetime | None = None,
) -> IntegrationSnapshot | None:
    get_scan_session(session, current_user, session_id)
    snapshot = _snapshot_for_update(session, session_id)
    if snapshot is None:
        session.commit()
        return None
    current_time = now or _utc_now()
    if (
        snapshot.status == "PENDING"
        and current_time - snapshot.updated_at >= PENDING_STALE_AFTER
    ):
        snapshot.status = "UNCERTAIN"
        snapshot.last_error_code = "PENDING_EXPIRED"
        snapshot.last_error_message = "导入过程异常中断，结果不确定，请人工核查"
        snapshot.updated_at = current_time
    session.commit()
    return snapshot


def import_completed_session(
    session: Session,
    current_user: AuthUser,
    session_id: int,
    *,
    config: JianDaoYunConfig,
    sender: Sender = create_registration,
    now: datetime | None = None,
) -> IntegrationSnapshot:
    if current_user.role == Role.VIEWER:
        raise ScanSessionForbiddenError("当前账号不能导入简道云")
    get_scan_session(session, current_user, session_id)
    current_time = now or _utc_now()
    batch = session.scalar(
        select(ScanSession).where(ScanSession.id == session_id).with_for_update()
    )
    if batch is None:
        session.rollback()
        raise RuntimeError("盘点批次不存在")

    snapshot = _snapshot_for_update(session, session_id)
    if snapshot is not None:
        completed = _prepare_existing_snapshot(
            session,
            snapshot,
            current_user,
            now=current_time,
        )
        if completed is not None:
            return completed
        payload = snapshot.payload_json
    else:
        export_data = build_export_data(session, current_user, session_id)
        payload = build_registration_data(export_data)
        snapshot = IntegrationSnapshot(
            session_id=session_id,
            payload_json=payload,
            payload_sha256=payload_sha256(payload),
            status="PENDING",
            external_data_id=None,
            attempt_count=1,
            last_error_code=None,
            last_error_message=None,
            created_by=current_user.id,
            last_attempted_by=current_user.id,
            created_at=current_time,
            updated_at=current_time,
            succeeded_at=None,
        )
        session.add(snapshot)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = _snapshot_for_update(session, session_id)
            if existing is None:
                session.rollback()
                raise
            completed = _prepare_existing_snapshot(
                session,
                existing,
                current_user,
                now=current_time,
            )
            if completed is not None:
                return completed
            payload = existing.payload_json

    try:
        result = sender(config, payload)
    except ExternalRejectedError as exc:
        _record_external_failure(
            session,
            session_id,
            status="FAILED",
            error_code="EXTERNAL_REJECTED",
            message=str(exc),
            now=current_time,
        )
        raise
    except ExternalUncertainError as exc:
        _record_external_failure(
            session,
            session_id,
            status="UNCERTAIN",
            error_code="EXTERNAL_UNCERTAIN",
            message=str(exc),
            now=current_time,
        )
        raise

    persisted = _snapshot_for_update(session, session_id)
    if persisted is None:
        session.rollback()
        raise RuntimeError("简道云快照不存在")
    persisted.status = "SUCCEEDED"
    persisted.external_data_id = result.data_id
    persisted.last_error_code = None
    persisted.last_error_message = None
    persisted.updated_at = current_time
    persisted.succeeded_at = current_time
    session.commit()
    return persisted
