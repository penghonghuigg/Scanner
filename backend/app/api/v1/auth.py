from fastapi import APIRouter, Request, Response

from app.api.dependencies import DatabaseSession
from app.auth.service import SESSION_COOKIE_NAME, authenticate_session, login, revoke_session
from app.core.errors import BusinessError
from app.schemas.auth import LoginRequest
from app.schemas.common import AuthPayload, EmptyPayload, SuccessEnvelope

router = APIRouter(prefix="/auth", tags=["auth"])


def require_allowed_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origin_set:
        raise BusinessError(403, "ORIGIN_NOT_ALLOWED", "请求来源不受信任")


@router.post("/login", response_model=SuccessEnvelope[AuthPayload])
def login_route(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> SuccessEnvelope[AuthPayload]:
    require_allowed_origin(request)
    result = login(
        session,
        username=payload.username,
        password=payload.password,
        ttl_hours=request.app.state.settings.session_ttl_hours,
    )
    if result is None:
        raise BusinessError(401, "AUTH_INVALID_CREDENTIALS", "用户名或密码错误")

    response.set_cookie(
        SESSION_COOKIE_NAME,
        result.session_token,
        max_age=result.max_age_seconds,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return SuccessEnvelope(
        data=AuthPayload(user=result.user),
        trace_id=request.state.trace_id,
    )


@router.get("/me", response_model=SuccessEnvelope[AuthPayload])
def me_route(
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> SuccessEnvelope[AuthPayload]:
    authenticated = authenticate_session(session, request.cookies.get(SESSION_COOKIE_NAME))
    if authenticated is None:
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        raise BusinessError(401, "AUTH_REQUIRED", "请先登录")
    _, user = authenticated
    return SuccessEnvelope(data=AuthPayload(user=user), trace_id=request.state.trace_id)


@router.post("/logout", response_model=SuccessEnvelope[EmptyPayload])
def logout_route(
    request: Request,
    response: Response,
    session: DatabaseSession,
) -> SuccessEnvelope[EmptyPayload]:
    require_allowed_origin(request)
    authenticated = authenticate_session(session, request.cookies.get(SESSION_COOKIE_NAME))
    if authenticated is not None:
        user_session, _ = authenticated
        revoke_session(session, user_session)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return SuccessEnvelope(data=EmptyPayload(), trace_id=request.state.trace_id)
