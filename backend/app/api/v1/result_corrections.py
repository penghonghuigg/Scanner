from fastapi import APIRouter, Query, Request

from app.api.dependencies import CurrentUser, DatabaseSession
from app.catalog.service import list_active_product_options
from app.core.errors import BusinessError
from app.scanning.result_service import (
    ProductInactiveError,
    ResultProductNotFoundError,
    ResultSessionNotCompletedError,
    add_result_item,
    replace_result_item,
)
from app.scanning.scan_service import (
    IdempotencyConflictError,
    ScanSessionItemNotFoundError,
    serialize_item,
    serialize_operation_event,
)
from app.scanning.service import ScanSessionForbiddenError, ScanSessionNotFoundError
from app.schemas.catalog import ProductOptionListPayload, ProductOptionResponse
from app.schemas.common import SuccessEnvelope
from app.schemas.finalization import (
    ResultItemCreateRequest,
    ResultItemOperationPayload,
    ResultItemReplaceRequest,
)

router = APIRouter(tags=["result-corrections"])


def require_allowed_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origin_set:
        raise BusinessError(403, "ORIGIN_NOT_ALLOWED", "请求来源不受信任")


def map_result_error(exc: ValueError) -> BusinessError:
    if isinstance(exc, ScanSessionForbiddenError):
        return BusinessError(403, "FORBIDDEN", str(exc))
    if isinstance(exc, ScanSessionNotFoundError):
        return BusinessError(404, "SCAN_SESSION_NOT_FOUND", str(exc))
    if isinstance(exc, ScanSessionItemNotFoundError):
        return BusinessError(404, "SCAN_SESSION_ITEM_NOT_FOUND", str(exc))
    if isinstance(exc, ResultProductNotFoundError):
        return BusinessError(404, "PRODUCT_NOT_FOUND", str(exc))
    if isinstance(exc, ProductInactiveError):
        return BusinessError(409, "PRODUCT_INACTIVE", str(exc))
    if isinstance(exc, ResultSessionNotCompletedError):
        return BusinessError(409, "RESULT_SESSION_NOT_COMPLETED", str(exc))
    if isinstance(exc, IdempotencyConflictError):
        return BusinessError(409, "IDEMPOTENCY_CONFLICT", str(exc))
    return BusinessError(422, "VALIDATION_ERROR", str(exc))


def operation_payload(
    session: DatabaseSession,
    result,
) -> ResultItemOperationPayload:
    return ResultItemOperationPayload.model_validate(
        {
            "item": serialize_item(result.item),
            "source_state": result.source_state,
            "event": serialize_operation_event(session, result.event),
            "idempotent_replay": result.idempotent_replay,
        }
    )


@router.get(
    "/product-options",
    response_model=SuccessEnvelope[ProductOptionListPayload],
)
def get_product_options(
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
    query: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
) -> SuccessEnvelope[ProductOptionListPayload]:
    del current_user
    result = list_active_product_options(
        session,
        query=query,
        page=page,
        page_size=page_size,
    )
    return SuccessEnvelope(
        data=ProductOptionListPayload(
            items=[
                ProductOptionResponse.model_validate(item, from_attributes=True)
                for item in result.items
            ],
            total=result.total,
            page=page,
            page_size=page_size,
        ),
        trace_id=request.state.trace_id,
    )


@router.post(
    "/scan-sessions/{session_id}/result-items",
    response_model=SuccessEnvelope[ResultItemOperationPayload],
)
def post_result_item(
    session_id: int,
    payload: ResultItemCreateRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ResultItemOperationPayload]:
    require_allowed_origin(request)
    try:
        result = add_result_item(
            session,
            current_user,
            session_id,
            request_id=str(payload.request_id),
            product_id=payload.product_id,
            quantity_cartons=payload.quantity_cartons,
            allocations=[item.model_dump() for item in payload.source_allocations],
        )
    except ValueError as exc:
        raise map_result_error(exc) from exc
    return SuccessEnvelope(
        data=operation_payload(session, result),
        trace_id=request.state.trace_id,
    )


@router.put(
    "/scan-sessions/{session_id}/result-items/{product_id}",
    response_model=SuccessEnvelope[ResultItemOperationPayload],
)
def put_result_item(
    session_id: int,
    product_id: int,
    payload: ResultItemReplaceRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ResultItemOperationPayload]:
    require_allowed_origin(request)
    try:
        result = replace_result_item(
            session,
            current_user,
            session_id,
            product_id,
            request_id=str(payload.request_id),
            quantity_cartons=payload.quantity_cartons,
            allocations=[item.model_dump() for item in payload.source_allocations],
        )
    except ValueError as exc:
        raise map_result_error(exc) from exc
    return SuccessEnvelope(
        data=operation_payload(session, result),
        trace_id=request.state.trace_id,
    )
