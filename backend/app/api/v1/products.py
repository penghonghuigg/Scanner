from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Query, Request, Response, UploadFile

from app.api.dependencies import CurrentUser, DatabaseSession
from app.catalog.excel import (
    MAX_FILE_SIZE,
    ImportFileInvalidError,
    build_import_template,
    import_products_from_workbook,
)
from app.catalog.service import (
    CartonCodeExistsError,
    CatalogValidationError,
    PackCodeConflictError,
    ProductNotFoundError,
    calculate_pack_price,
    calculate_sticks_per_carton,
    create_product,
    is_pack_code_ambiguous,
    list_products,
    update_product,
)
from app.core.errors import BusinessError
from app.models.catalog import CigaretteProduct
from app.schemas.catalog import (
    CreateProductRequest,
    ImportIssueResponse,
    ProductImportPayload,
    ProductListPayload,
    ProductPayload,
    ProductResponse,
    ProductSummary,
    UpdateProductRequest,
)
from app.schemas.common import SuccessEnvelope

router = APIRouter(prefix="/products", tags=["products"])
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def require_admin(current_user: CurrentUser) -> None:
    if current_user.role != "ADMIN":
        raise BusinessError(403, "FORBIDDEN", "仅管理员可以管理品规")


def require_allowed_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origin_set:
        raise BusinessError(403, "ORIGIN_NOT_ALLOWED", "请求来源不受信任")


def product_response(session: DatabaseSession, product: CigaretteProduct) -> ProductResponse:
    return ProductResponse(
        id=product.id,
        carton_code=product.carton_code,
        pack_code=product.pack_code,
        brand=product.brand,
        standard_name=product.standard_name,
        carton_retail_price=product.carton_retail_price,
        pack_retail_price=calculate_pack_price(
            product.carton_retail_price,
            product.packs_per_carton,
        ),
        sticks_per_pack=product.sticks_per_pack,
        packs_per_carton=product.packs_per_carton,
        sticks_per_carton=calculate_sticks_per_carton(
            product.sticks_per_pack,
            product.packs_per_carton,
        ),
        is_pack_ambiguous=is_pack_code_ambiguous(session, product.pack_code),
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


def map_catalog_error(exc: ValueError) -> BusinessError:
    if isinstance(exc, ProductNotFoundError):
        return BusinessError(404, "PRODUCT_NOT_FOUND", str(exc))
    if isinstance(exc, CartonCodeExistsError):
        return BusinessError(409, "CARTON_CODE_EXISTS", str(exc))
    if isinstance(exc, PackCodeConflictError):
        return BusinessError(409, "PACK_CODE_CONFLICT", str(exc))
    if isinstance(exc, CatalogValidationError):
        return BusinessError(422, "VALIDATION_ERROR", str(exc))
    return BusinessError(422, "VALIDATION_ERROR", "品规数据不符合要求")


@router.get("", response_model=SuccessEnvelope[ProductListPayload])
def get_products(
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
    query: str = Query(default="", max_length=100),
    is_active: bool | None = None,
    ambiguous: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> SuccessEnvelope[ProductListPayload]:
    require_admin(current_user)
    result = list_products(
        session,
        query=query,
        is_active=is_active,
        ambiguous=ambiguous,
        page=page,
        page_size=page_size,
    )
    return SuccessEnvelope(
        data=ProductListPayload(
            items=[product_response(session, item) for item in result.items],
            total=result.total,
            page=page,
            page_size=page_size,
            summary=ProductSummary(
                total_count=result.total_count,
                active_count=result.active_count,
                inactive_count=result.inactive_count,
                ambiguous_count=result.ambiguous_count,
            ),
        ),
        trace_id=request.state.trace_id,
    )


@router.post("", status_code=201, response_model=SuccessEnvelope[ProductPayload])
def post_product(
    payload: CreateProductRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ProductPayload]:
    require_admin(current_user)
    require_allowed_origin(request)
    try:
        product = create_product(session, **payload.model_dump())
    except ValueError as exc:
        raise map_catalog_error(exc) from exc
    return SuccessEnvelope(
        data=ProductPayload(product=product_response(session, product)),
        trace_id=request.state.trace_id,
    )


@router.patch("/{product_id}", response_model=SuccessEnvelope[ProductPayload])
def patch_product(
    product_id: int,
    payload: UpdateProductRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[ProductPayload]:
    require_admin(current_user)
    require_allowed_origin(request)
    try:
        product = update_product(
            session,
            product_id,
            **payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise map_catalog_error(exc) from exc
    return SuccessEnvelope(
        data=ProductPayload(product=product_response(session, product)),
        trace_id=request.state.trace_id,
    )


@router.get("/import-template.xlsx")
def get_import_template(
    current_user: CurrentUser,
) -> Response:
    require_admin(current_user)
    filename = quote("卷烟品规导入模板.xlsx")
    return Response(
        content=build_import_template(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/import", response_model=SuccessEnvelope[ProductImportPayload])
async def import_products(
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
    file: Annotated[UploadFile, File()],
) -> SuccessEnvelope[ProductImportPayload]:
    require_admin(current_user)
    require_allowed_origin(request)
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise BusinessError(422, "IMPORT_FILE_INVALID", "只允许上传 .xlsx 文件")
    if file.content_type not in {XLSX_MEDIA_TYPE, "application/octet-stream"}:
        raise BusinessError(422, "IMPORT_FILE_INVALID", "Excel MIME 类型不正确")
    content = await file.read(MAX_FILE_SIZE + 1)
    try:
        result = import_products_from_workbook(session, content)
    except ImportFileInvalidError as exc:
        raise BusinessError(422, "IMPORT_FILE_INVALID", str(exc)) from exc
    return SuccessEnvelope(
        data=ProductImportPayload(
            total_rows=result.total_rows,
            created_count=result.created_count,
            updated_count=result.updated_count,
            skipped_count=result.skipped_count,
            warning_count=result.warning_count,
            issues=[ImportIssueResponse.model_validate(issue) for issue in result.issues],
        ),
        trace_id=request.state.trace_id,
    )
