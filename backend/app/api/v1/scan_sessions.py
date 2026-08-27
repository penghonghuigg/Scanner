from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUser, DatabaseSession
from app.core.errors import BusinessError
from app.scanning.scan_service import (
    AmbiguityAlreadyResolvedError,
    AmbiguityCandidateInvalidError,
    BarcodeInvalidError,
    IdempotencyConflictError,
    ScanEventNotFoundError,
    ScanSessionClosedError,
    get_scan_state,
    resolve_ambiguity,
    scan_code,
    serialize_operation_event,
)
from app.scanning.service import (
    BranchInvalidError,
    BranchRequiredError,
    BusinessTypeInvalidError,
    ScanSessionCreateFailedError,
    ScanSessionForbiddenError,
    ScanSessionNotFoundError,
    create_scan_session,
    get_scan_session,
    list_scan_sessions,
    serialize_scan_session,
)
from app.schemas.common import SuccessEnvelope
from app.schemas.scanning import (
    CreateScanSessionRequest,
    ResolveAmbiguityRequest,
    ScanCodeRequest,
    ScanOperationResponse,
    ScanSessionListPayload,
    ScanSessionPayload,
    ScanSessionResponse,
    ScanStateResponse,
)

router = APIRouter(prefix="/scan-sessions", tags=["scan-sessions"])


def require_allowed_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origin_set:
        raise BusinessError(403, "ORIGIN_NOT_ALLOWED", "请求来源不受信任")


def map_scanning_error(exc: Exception) -> BusinessError:
    if isinstance(exc, BusinessTypeInvalidError):
        return BusinessError(422, "BUSINESS_TYPE_INVALID", str(exc))
    if isinstance(exc, BranchRequiredError):
        return BusinessError(422, "BRANCH_REQUIRED", str(exc))
    if isinstance(exc, BranchInvalidError):
        return BusinessError(422, "BRANCH_INVALID", str(exc))
    if isinstance(exc, ScanSessionForbiddenError):
        return BusinessError(403, "FORBIDDEN", str(exc))
    if isinstance(exc, ScanSessionNotFoundError):
        return BusinessError(404, "SCAN_SESSION_NOT_FOUND", str(exc))
    if isinstance(exc, ScanSessionCreateFailedError):
        return BusinessError(503, "SCAN_SESSION_CREATE_FAILED", str(exc))
    if isinstance(exc, BarcodeInvalidError):
        return BusinessError(422, "BARCODE_INVALID", str(exc))
    if isinstance(exc, ScanSessionClosedError):
        return BusinessError(409, "SCAN_SESSION_CLOSED", str(exc))
    if isinstance(exc, IdempotencyConflictError):
        return BusinessError(409, "IDEMPOTENCY_CONFLICT", str(exc))
    if isinstance(exc, ScanEventNotFoundError):
        return BusinessError(404, "SCAN_EVENT_NOT_FOUND", str(exc))
    if isinstance(exc, AmbiguityAlreadyResolvedError):
        return BusinessError(409, "AMBIGUITY_ALREADY_RESOLVED", str(exc))
    if isinstance(exc, AmbiguityCandidateInvalidError):
        return BusinessError(422, "AMBIGUITY_CANDIDATE_INVALID", str(exc))
    return BusinessError(422, "VALIDATION_ERROR", "扫描批次数据不符合要求")


def response_model(session: DatabaseSession, model) -> ScanSessionResponse:
    return ScanSessionResponse.model_validate(serialize_scan_session(session, model))


@router.post("", status_code=201, response_model=SuccessEnvelope[ScanSessionPayload])
def post_scan_session(
    payload: CreateScanSessionRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ScanSessionPayload]:
    require_allowed_origin(request)
    try:
        model = create_scan_session(
            session,
            current_user,
            payload.model_dump(),
        )
    except (ValueError, RuntimeError) as exc:
        raise map_scanning_error(exc) from exc
    return SuccessEnvelope(
        data=ScanSessionPayload(scan_session=response_model(session, model)),
        trace_id=request.state.trace_id,
    )


@router.get("", response_model=SuccessEnvelope[ScanSessionListPayload])
def get_scan_sessions(
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
    query: str = Query(default="", max_length=100),
    business_type: str | None = Query(default=None, max_length=32),
    status: str | None = Query(default=None, max_length=16),
    branch_code: str | None = Query(default=None, max_length=20),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SuccessEnvelope[ScanSessionListPayload]:
    try:
        result = list_scan_sessions(
            session,
            current_user,
            {
                "query": query,
                "business_type": business_type,
                "status": status,
                "branch_code": branch_code,
            },
            page,
            page_size,
        )
    except ValueError as exc:
        raise map_scanning_error(exc) from exc
    return SuccessEnvelope(
        data=ScanSessionListPayload(
            items=[response_model(session, item) for item in result.items],
            total=result.total,
            page=page,
            page_size=page_size,
        ),
        trace_id=request.state.trace_id,
    )


@router.get("/{session_id}", response_model=SuccessEnvelope[ScanSessionPayload])
def get_scan_session_detail(
    session_id: int,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ScanSessionPayload]:
    try:
        model = get_scan_session(session, current_user, session_id)
    except ValueError as exc:
        raise map_scanning_error(exc) from exc
    return SuccessEnvelope(
        data=ScanSessionPayload(scan_session=response_model(session, model)),
        trace_id=request.state.trace_id,
    )


def scan_state_response(
    session: DatabaseSession,
    current_user: CurrentUser,
    session_id: int,
) -> ScanStateResponse:
    return ScanStateResponse.model_validate(get_scan_state(session, current_user, session_id))


def operation_response(
    session: DatabaseSession,
    current_user: CurrentUser,
    session_id: int,
    event,
    idempotent_replay: bool,
) -> ScanOperationResponse:
    state = scan_state_response(session, current_user, session_id)
    return ScanOperationResponse(
        event=serialize_operation_event(session, event),
        state=state,
        idempotent_replay=idempotent_replay,
    )


@router.post(
    "/{session_id}/scan",
    response_model=SuccessEnvelope[ScanOperationResponse],
)
def post_scan_code(
    session_id: int,
    payload: ScanCodeRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ScanOperationResponse]:
    require_allowed_origin(request)
    try:
        result = scan_code(
            session,
            current_user,
            session_id,
            str(payload.request_id),
            payload.code,
        )
        data = operation_response(
            session,
            current_user,
            session_id,
            result.event,
            result.idempotent_replay,
        )
    except ValueError as exc:
        raise map_scanning_error(exc) from exc
    return SuccessEnvelope(data=data, trace_id=request.state.trace_id)


@router.post(
    "/{session_id}/resolve",
    response_model=SuccessEnvelope[ScanOperationResponse],
)
def post_resolve_ambiguity(
    session_id: int,
    payload: ResolveAmbiguityRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ScanOperationResponse]:
    require_allowed_origin(request)
    try:
        result = resolve_ambiguity(
            session,
            current_user,
            session_id,
            str(payload.request_id),
            payload.event_id,
            payload.product_id,
        )
        data = operation_response(
            session,
            current_user,
            session_id,
            result.event,
            result.idempotent_replay,
        )
    except ValueError as exc:
        raise map_scanning_error(exc) from exc
    return SuccessEnvelope(data=data, trace_id=request.state.trace_id)


@router.get(
    "/{session_id}/scan-state",
    response_model=SuccessEnvelope[ScanStateResponse],
)
def get_session_scan_state(
    session_id: int,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ScanStateResponse]:
    try:
        data = scan_state_response(session, current_user, session_id)
    except ValueError as exc:
        raise map_scanning_error(exc) from exc
    return SuccessEnvelope(data=data, trace_id=request.state.trace_id)
