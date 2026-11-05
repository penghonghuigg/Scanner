from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUser, DatabaseSession
from app.core.errors import BusinessError
from app.integrations.jiandaoyun import (
    ExternalRejectedError,
    ExternalUncertainError,
    JianDaoYunConfig,
)
from app.integrations.service import (
    IntegrationInProgressError,
    IntegrationUncertainError,
    get_integration_snapshot,
    import_completed_session,
)
from app.scanning.export_service import ExportEmptyError, ExportSessionNotCompletedError
from app.scanning.service import ScanSessionForbiddenError, ScanSessionNotFoundError
from app.schemas.common import SuccessEnvelope
from app.schemas.integration import IntegrationSnapshotPayload, IntegrationSnapshotResponse

router = APIRouter(prefix="/scan-sessions", tags=["integration"])


def require_allowed_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origin_set:
        raise BusinessError(403, "ORIGIN_NOT_ALLOWED", "请求来源不受信任")


def integration_config(request: Request) -> JianDaoYunConfig:
    settings = request.app.state.settings
    try:
        return JianDaoYunConfig(
            create_url=settings.jiandaoyun_create_url,
            app_id=settings.jiandaoyun_app_id,
            entry_id=settings.jiandaoyun_entry_id,
            api_key=settings.jiandaoyun_api_key,
        )
    except ValueError as exc:
        raise BusinessError(
            409,
            "INTEGRATION_NOT_CONFIGURED",
            "简道云接口尚未完成配置",
        ) from exc


def map_integration_error(exc: Exception) -> BusinessError:
    if isinstance(exc, ScanSessionForbiddenError):
        return BusinessError(403, "FORBIDDEN", str(exc))
    if isinstance(exc, ScanSessionNotFoundError):
        return BusinessError(404, "SCAN_SESSION_NOT_FOUND", str(exc))
    if isinstance(exc, ExportSessionNotCompletedError):
        return BusinessError(409, "INTEGRATION_SESSION_NOT_COMPLETED", str(exc))
    if isinstance(exc, ExportEmptyError):
        return BusinessError(422, "INTEGRATION_EMPTY", str(exc))
    if isinstance(exc, IntegrationInProgressError):
        return BusinessError(409, "INTEGRATION_IN_PROGRESS", str(exc))
    if isinstance(exc, IntegrationUncertainError):
        return BusinessError(409, "INTEGRATION_UNCERTAIN", str(exc))
    if isinstance(exc, ExternalRejectedError):
        return BusinessError(502, "INTEGRATION_EXTERNAL_REJECTED", str(exc))
    if isinstance(exc, ExternalUncertainError):
        return BusinessError(504, "INTEGRATION_EXTERNAL_UNCERTAIN", str(exc))
    return BusinessError(422, "INTEGRATION_EMPTY", "批次没有可导入的有效品规")


def snapshot_payload(model) -> IntegrationSnapshotPayload:
    return IntegrationSnapshotPayload(
        snapshot=(
            IntegrationSnapshotResponse.model_validate(model)
            if model is not None
            else None
        )
    )


@router.get(
    "/{session_id}/integration-snapshot",
    response_model=SuccessEnvelope[IntegrationSnapshotPayload],
)
def get_snapshot_route(
    session_id: int,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[IntegrationSnapshotPayload]:
    try:
        model = get_integration_snapshot(session, current_user, session_id)
    except ValueError as exc:
        raise map_integration_error(exc) from exc
    return SuccessEnvelope(
        data=snapshot_payload(model),
        trace_id=request.state.trace_id,
    )


@router.post(
    "/{session_id}/jiandaoyun-import",
    response_model=SuccessEnvelope[IntegrationSnapshotPayload],
)
def post_jiandaoyun_import(
    session_id: int,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[IntegrationSnapshotPayload]:
    require_allowed_origin(request)
    config = integration_config(request)
    try:
        model = import_completed_session(
            session,
            current_user,
            session_id,
            config=config,
        )
    except (
        ValueError,
        IntegrationInProgressError,
        IntegrationUncertainError,
        ExternalRejectedError,
        ExternalUncertainError,
    ) as exc:
        raise map_integration_error(exc) from exc
    return SuccessEnvelope(
        data=snapshot_payload(model),
        trace_id=request.state.trace_id,
    )
