from fastapi import APIRouter, Request

from app.api.dependencies import CurrentUser, DatabaseSession
from app.core.errors import BusinessError
from app.schemas.common import AuthPayload, SuccessEnvelope
from app.schemas.users import CreateUserRequest
from app.users.service import (
    BranchInvalidError,
    PasswordMismatchError,
    RegistrationValidationError,
    UsernameExistsError,
    create_operator,
)

router = APIRouter(prefix="/users", tags=["users"])


def require_allowed_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origin_set:
        raise BusinessError(403, "ORIGIN_NOT_ALLOWED", "请求来源不受信任")


@router.post("", status_code=201, response_model=SuccessEnvelope[AuthPayload])
def register_user(
    payload: CreateUserRequest,
    request: Request,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> SuccessEnvelope[AuthPayload]:
    require_allowed_origin(request)
    if current_user.role != "ADMIN":
        raise BusinessError(403, "FORBIDDEN", "无人员注册权限")
    try:
        user = create_operator(session, **payload.model_dump())
    except UsernameExistsError as exc:
        raise BusinessError(409, "USERNAME_EXISTS", str(exc)) from exc
    except BranchInvalidError as exc:
        raise BusinessError(422, "BRANCH_INVALID", str(exc)) from exc
    except PasswordMismatchError as exc:
        raise BusinessError(422, "PASSWORD_MISMATCH", str(exc)) from exc
    except RegistrationValidationError as exc:
        raise BusinessError(422, "VALIDATION_ERROR", str(exc)) from exc
    return SuccessEnvelope(data=AuthPayload(user=user), trace_id=request.state.trace_id)
