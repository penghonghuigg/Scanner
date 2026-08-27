import argparse
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth.branches import BRANCH_NAMES
from app.core.config import Settings
from app.core.security import hash_password
from app.models.auth import Role, User


class DuplicateUsernameError(ValueError):
    pass


def create_user(
    *,
    database_url: str,
    username: str,
    display_name: str,
    role: str,
    password: str,
    branch_code: str | None = None,
) -> int:
    normalized_username = username.strip().lower()
    normalized_display_name = display_name.strip()
    if not normalized_username or not normalized_display_name or not password:
        raise ValueError("用户名、显示名称和密码不能为空")
    if role not in {member.value for member in Role}:
        raise ValueError("角色必须是 ADMIN、OPERATOR 或 VIEWER")
    if role == Role.ADMIN and branch_code is not None:
        raise ValueError("管理员不能绑定分局")
    if role != Role.ADMIN and branch_code not in BRANCH_NAMES:
        raise ValueError("非管理员必须绑定有效分局")

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session, session.begin():
            if session.scalar(select(User.id).where(User.username == normalized_username)):
                raise DuplicateUsernameError(f"用户名已存在：{normalized_username}")
            user = User(
                username=normalized_username,
                password_hash=hash_password(password),
                display_name=normalized_display_name,
                role=role,
                branch_code=branch_code,
            )
            session.add(user)
            session.flush()
            return user.id
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="创建系统登录用户")
    parser.add_argument("--username", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=[role.value for role in Role], required=True)
    parser.add_argument("--branch-code", choices=sorted(BRANCH_NAMES))
    parser.add_argument("--password-stdin", action="store_true", required=True)
    arguments = parser.parse_args()
    password = sys.stdin.readline().rstrip("\r\n")
    if not password:
        parser.error("标准输入中的密码不能为空")

    user_id = create_user(
        database_url=Settings().database_url,
        username=arguments.username,
        display_name=arguments.display_name,
        role=arguments.role,
        branch_code=arguments.branch_code,
        password=password,
    )
    print(f"用户创建成功，ID={user_id}")


if __name__ == "__main__":
    main()
