import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.branches import BRANCH_NAMES
from app.auth.service import to_auth_user
from app.core.security import hash_password
from app.models.auth import User
from app.schemas.auth import AuthUser

USERNAME_PATTERN = re.compile(r"[a-z0-9_.-]{3,64}")


class UsernameExistsError(ValueError):
    pass


class BranchInvalidError(ValueError):
    pass


class PasswordMismatchError(ValueError):
    pass


class RegistrationValidationError(ValueError):
    pass


def create_operator(
    session: Session,
    *,
    username: str,
    display_name: str,
    branch_code: str,
    password: str,
    password_confirmation: str,
) -> AuthUser:
    normalized_username = username.strip().lower()
    normalized_display_name = display_name.strip()
    if not USERNAME_PATTERN.fullmatch(normalized_username) or not normalized_display_name:
        raise RegistrationValidationError("账号或姓名格式不正确")
    if branch_code not in BRANCH_NAMES:
        raise BranchInvalidError("所属分局无效")
    if password != password_confirmation:
        raise PasswordMismatchError("两次输入的密码不一致")
    if session.scalar(select(User.id).where(User.username == normalized_username)) is not None:
        raise UsernameExistsError("登录账号已存在")

    user = User(
        username=normalized_username,
        password_hash=hash_password(password),
        display_name=normalized_display_name,
        role="OPERATOR",
        branch_code=branch_code,
        is_active=True,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise UsernameExistsError("登录账号已存在") from exc
    session.refresh(user)
    return to_auth_user(user)
