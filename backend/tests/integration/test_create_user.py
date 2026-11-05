import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.cli.create_user import DuplicateUsernameError, create_user
from app.core.security import verify_password
from app.db.schema import initialize_database
from app.models.auth import User, UserSession
from app.models.finalization import ExportRecord, ScanItemSourceAllocation
from app.models.integration import IntegrationSnapshot
from app.models.scanning import ScanEvent, ScanSession, ScanSessionItem

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def reset_auth_tables() -> None:
    database_url = database_url_for_test()
    initialize_database(database_url)
    engine = create_engine(database_url)
    with Session(engine) as session, session.begin():
        session.execute(delete(ExportRecord))
        session.execute(delete(ScanItemSourceAllocation))
        session.execute(delete(ScanEvent).where(ScanEvent.source_event_id.is_not(None)))
        session.execute(delete(ScanEvent))
        session.execute(delete(ScanSessionItem))
        session.execute(delete(UserSession))
        session.execute(delete(IntegrationSnapshot))
        session.execute(delete(ScanSession))
        session.execute(delete(User))
    engine.dispose()


def test_create_user_normalizes_username_and_hashes_password() -> None:
    reset_auth_tables()

    user_id = create_user(
        database_url=database_url_for_test(),
        username=" Admin ",
        display_name="系统管理员",
        role="ADMIN",
        password="correct-password",
    )

    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.id == user_id))
        assert user is not None
        assert user.username == "admin"
        assert user.password_hash != "correct-password"
        assert verify_password(user.password_hash, "correct-password")
    engine.dispose()


def test_create_user_rejects_duplicate_username() -> None:
    reset_auth_tables()
    arguments = {
        "database_url": database_url_for_test(),
        "username": "admin",
        "display_name": "系统管理员",
        "role": "ADMIN",
        "password": "correct-password",
    }
    create_user(**arguments)

    with pytest.raises(DuplicateUsernameError):
        create_user(**arguments)


def test_create_operator_requires_and_saves_an_approved_branch() -> None:
    reset_auth_tables()

    user_id = create_user(
        database_url=database_url_for_test(),
        username="operator",
        display_name="操作人员",
        role="OPERATOR",
        branch_code="PANJI",
        password="correct-password",
    )

    engine = create_engine(database_url_for_test())
    with Session(engine) as session:
        user = session.scalar(select(User).where(User.id == user_id))
        assert user is not None
        assert user.branch_code == "PANJI"
    engine.dispose()
