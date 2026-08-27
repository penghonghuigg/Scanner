from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.service import SESSION_COOKIE_NAME, authenticate_session
from app.core.errors import BusinessError
from app.schemas.auth import AuthUser


def get_database_session(request: Request) -> Generator[Session, None, None]:
    with request.app.state.session_factory() as session:
        yield session


DatabaseSession = Annotated[Session, Depends(get_database_session)]


def get_current_user(request: Request, session: DatabaseSession) -> AuthUser:
    authenticated = authenticate_session(session, request.cookies.get(SESSION_COOKIE_NAME))
    if authenticated is None:
        raise BusinessError(401, "AUTH_REQUIRED", "请先登录")
    return authenticated[1]


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
