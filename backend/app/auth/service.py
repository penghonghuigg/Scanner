from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.branches import branch_name
from app.core.security import digest_token, generate_token, verify_password
from app.models.auth import User, UserSession
from app.schemas.auth import AuthUser

SESSION_COOKIE_NAME = "scanner_session"


@dataclass(frozen=True)
class LoginResult:
    user: AuthUser
    session_token: str
    max_age_seconds: int


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def to_auth_user(user: User) -> AuthUser:
    return AuthUser(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        branch_code=user.branch_code,
        branch_name=branch_name(user.branch_code),
    )


def login(
    session: Session,
    *,
    username: str,
    password: str,
    ttl_hours: int,
) -> LoginResult | None:
    normalized_username = username.strip().lower()
    user = session.scalar(select(User).where(User.username == normalized_username))
    if user is None or not user.is_active or not verify_password(user.password_hash, password):
        return None

    raw_token = generate_token()
    max_age_seconds = ttl_hours * 60 * 60
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=digest_token(raw_token),
            expires_at=utc_now_naive() + timedelta(seconds=max_age_seconds),
        )
    )
    session.commit()
    return LoginResult(to_auth_user(user), raw_token, max_age_seconds)


def authenticate_session(
    session: Session,
    raw_token: str | None,
) -> tuple[UserSession, AuthUser] | None:
    if not raw_token:
        return None
    row = session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(
            UserSession.token_hash == digest_token(raw_token),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > utc_now_naive(),
            User.is_active.is_(True),
        )
    ).one_or_none()
    if row is None:
        return None
    user_session, user = row
    return user_session, to_auth_user(user)


def revoke_session(session: Session, user_session: UserSession) -> None:
    user_session.revoked_at = utc_now_naive()
    session.commit()
