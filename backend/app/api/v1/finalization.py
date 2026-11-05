from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Request, Response

from app.api.dependencies import CurrentUser, DatabaseSession
from app.core.errors import BusinessError
from app.scanning.completion_service import (
    ExceptionConfirmationRequiredError,
    FinalizationEmptyError,
    SourceAllocationRequiredError,
    complete_scan_session,
)
from app.scanning.export_service import (
    ExportEmptyError,
    ExportSessionNotCompletedError,
    generate_session_export,
)
from app.scanning.regions import (
    SOURCE_TYPE_NAMES,
    SourceLocationInvalidError,
    region_catalog,
)
from app.scanning.scan_service import ScanSessionClosedError, ScanSessionItemNotFoundError
from app.scanning.service import (
    ScanSessionForbiddenError,
    ScanSessionNotFoundError,
    serialize_scan_session,
)
from app.scanning.source_service import (
    QuantityNotPackAlignedError,
    SourceQuantityMismatchError,
    list_source_allocations,
    replace_source_allocations,
)
from app.schemas.common import SuccessEnvelope
from app.schemas.finalization import (
    CompleteScanSessionRequest,
    CompletionSummaryResponse,
    ProductSourceAllocationState,
    RegionCatalogPayload,
    RegionCity,
    RegionProvince,
    SourceAllocationListPayload,
    SourceAllocationReplaceRequest,
    SourceTypeOption,
)

router = APIRouter(tags=["finalization"])


def require_allowed_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origin_set:
        raise BusinessError(403, "ORIGIN_NOT_ALLOWED", "请求来源不受信任")


def map_finalization_error(exc: Exception) -> BusinessError:
    if isinstance(exc, ScanSessionForbiddenError):
        return BusinessError(403, "FORBIDDEN", str(exc))
    if isinstance(exc, ScanSessionNotFoundError):
        return BusinessError(404, "SCAN_SESSION_NOT_FOUND", str(exc))
    if isinstance(exc, ScanSessionItemNotFoundError):
        return BusinessError(404, "SCAN_SESSION_ITEM_NOT_FOUND", str(exc))
    if isinstance(exc, ScanSessionClosedError):
        return BusinessError(409, "SCAN_SESSION_CLOSED", str(exc))
    if isinstance(exc, SourceLocationInvalidError):
        return BusinessError(422, "SOURCE_LOCATION_INVALID", str(exc))
    if isinstance(exc, SourceQuantityMismatchError):
        return BusinessError(422, "SOURCE_QUANTITY_MISMATCH", str(exc))
    if isinstance(exc, QuantityNotPackAlignedError):
        return BusinessError(422, "QUANTITY_NOT_PACK_ALIGNED", str(exc))
    if isinstance(exc, SourceAllocationRequiredError):
        return BusinessError(409, "SOURCE_ALLOCATION_REQUIRED", str(exc))
    if isinstance(exc, ExceptionConfirmationRequiredError):
        return BusinessError(409, "EXCEPTION_CONFIRMATION_REQUIRED", str(exc))
    if isinstance(exc, FinalizationEmptyError):
        return BusinessError(422, "EXPORT_EMPTY", str(exc))
    if isinstance(exc, ExportSessionNotCompletedError):
        return BusinessError(409, "EXPORT_SESSION_NOT_COMPLETED", str(exc))
    if isinstance(exc, ExportEmptyError):
        return BusinessError(422, "EXPORT_EMPTY", str(exc))
    return BusinessError(422, "VALIDATION_ERROR", "批次核对数据不符合要求")


@router.get("/regions", response_model=SuccessEnvelope[RegionCatalogPayload])
def get_regions(
    request: Request,
    current_user: CurrentUser,
) -> SuccessEnvelope[RegionCatalogPayload]:
    del current_user
    return SuccessEnvelope(
        data=RegionCatalogPayload(
            source_types=[
                SourceTypeOption(value=value, label=label)
                for value, label in SOURCE_TYPE_NAMES.items()
            ],
            provinces=[
                RegionProvince(
                    name=str(province["name"]),
                    cities=[RegionCity(name=str(city)) for city in province["cities"]],
                )
                for province in region_catalog()
            ],
        ),
        trace_id=request.state.trace_id,
    )


@router.get(
    "/scan-sessions/{session_id}/source-allocations",
    response_model=SuccessEnvelope[SourceAllocationListPayload],
)
def get_session_source_allocations(
    session_id: int,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[SourceAllocationListPayload]:
    try:
        items = list_source_allocations(session, current_user, session_id)
    except ValueError as exc:
        raise map_finalization_error(exc) from exc
    return SuccessEnvelope(
        data=SourceAllocationListPayload.model_validate({"items": items}),
        trace_id=request.state.trace_id,
    )


@router.put(
    "/scan-sessions/{session_id}/items/{product_id}/source-allocations",
    response_model=SuccessEnvelope[ProductSourceAllocationState],
)
def put_product_source_allocations(
    session_id: int,
    product_id: int,
    payload: SourceAllocationReplaceRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ProductSourceAllocationState]:
    require_allowed_origin(request)
    try:
        state = replace_source_allocations(
            session,
            current_user,
            session_id,
            product_id,
            [item.model_dump() for item in payload.items],
        )
    except ValueError as exc:
        raise map_finalization_error(exc) from exc
    return SuccessEnvelope(
        data=ProductSourceAllocationState.model_validate(state),
        trace_id=request.state.trace_id,
    )


@router.post(
    "/scan-sessions/{session_id}/complete",
    response_model=SuccessEnvelope[CompletionSummaryResponse],
)
def post_complete_scan_session(
    session_id: int,
    payload: CompleteScanSessionRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[CompletionSummaryResponse]:
    require_allowed_origin(request)
    try:
        result = complete_scan_session(
            session,
            current_user,
            session_id,
            confirm_exceptions=payload.confirm_exceptions,
        )
    except ValueError as exc:
        raise map_finalization_error(exc) from exc
    return SuccessEnvelope(
        data=CompletionSummaryResponse.model_validate(
            {
                "scan_session": serialize_scan_session(session, result.scan_session),
                "summary": result.summary,
                "source_product_count": result.source_product_count,
                "source_allocated_product_count": result.source_allocated_product_count,
                "unknown_count": result.unknown_count,
                "unresolved_ambiguity_count": result.unresolved_ambiguity_count,
            }
        ),
        trace_id=request.state.trace_id,
    )


@router.get("/scan-sessions/{session_id}/export.xlsx")
def get_scan_session_export(
    session_id: int,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> Response:
    try:
        generated = generate_session_export(
            session,
            current_user,
            session_id,
            now=datetime.now(UTC).replace(tzinfo=None),
        )
    except ValueError as exc:
        raise map_finalization_error(exc) from exc
    encoded_filename = quote(generated.filename)
    return Response(
        content=generated.content,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                f"attachment; filename=scan-session-{session_id}.xlsx; "
                f"filename*=UTF-8''{encoded_filename}"
            )
        },
    )
