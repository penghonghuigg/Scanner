from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class BusinessError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def business_error_handler(request: Request, exc: BusinessError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {"code": exc.code, "message": exc.message},
            "trace_id": request.state.trace_id,
        },
    )


def request_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    path_parts = request.url.path.strip("/").split("/")
    is_scan_code_error = (
        request.method == "POST"
        and len(path_parts) == 5
        and path_parts[:3] == ["api", "v1", "scan-sessions"]
        and path_parts[-1] == "scan"
        and any(tuple(error["loc"]) == ("body", "code") for error in exc.errors())
    )
    if is_scan_code_error:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {"code": "BARCODE_INVALID", "message": "编码必须为 6～64 位数字"},
                "trace_id": request.state.trace_id,
            },
        )
    is_adjustment_error = (
        request.method == "POST"
        and len(path_parts) == 7
        and path_parts[:3] == ["api", "v1", "scan-sessions"]
        and path_parts[-1] == "carton-quantity"
        and any(
            tuple(error["loc"]) == ("body", "reason_type")
            or (
                tuple(error["loc"]) == ("body",)
                and isinstance(error.get("input"), dict)
                and error["input"].get("reason_type") == "OTHER"
            )
            for error in exc.errors()
        )
    )
    if is_adjustment_error:
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "ADJUSTMENT_REASON_REQUIRED",
                    "message": "请选择或填写人工调整原因",
                },
                "trace_id": request.state.trace_id,
            },
        )
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {"code": "VALIDATION_ERROR", "message": "请求参数不符合要求"},
            "trace_id": request.state.trace_id,
        },
    )
