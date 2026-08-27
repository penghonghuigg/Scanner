from sqlalchemy.dialects import mysql

from app.db.base import Base
from app.models import auth  # noqa: F401


def test_metadata_contains_tables_through_stage_five() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "user_sessions",
        "cigarette_products",
        "scan_sessions",
        "scan_events",
        "scan_session_items",
    }


def test_users_and_sessions_match_the_lightweight_contract() -> None:
    users = Base.metadata.tables["users"]
    sessions = Base.metadata.tables["user_sessions"]

    assert set(users.c.keys()) == {
        "id",
        "username",
        "password_hash",
        "display_name",
        "role",
        "branch_code",
        "is_active",
        "created_at",
        "updated_at",
    }
    assert users.c.id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert users.c.username.unique is True
    assert users.c.branch_code.type.length == 20
    assert users.c.branch_code.nullable is True
    assert {index.name for index in users.indexes} == {"idx_users_branch"}
    assert {constraint.name for constraint in users.constraints} >= {
        "ck_users_role",
        "ck_users_branch",
    }
    assert set(sessions.c.keys()) == {
        "id",
        "user_id",
        "token_hash",
        "expires_at",
        "revoked_at",
        "created_at",
    }
    assert sessions.c.token_hash.unique is True
    assert {index.name for index in sessions.indexes} == {"idx_user_sessions_user_active"}


def test_auth_tables_use_mysql_persistent_options() -> None:
    for table_name in ("users", "user_sessions"):
        table = Base.metadata.tables[table_name]
        assert table.dialect_options["mysql"]["engine"] == "InnoDB"
        assert table.dialect_options["mysql"]["charset"] == "utf8mb4"
        assert table.dialect_options["mysql"]["collate"] == "utf8mb4_0900_ai_ci"
