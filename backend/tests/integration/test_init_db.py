import os
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

from app.db.schema import initialize_database

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def database_url_for_test() -> str:
    load_dotenv(REPOSITORY_ROOT / ".env")
    value = os.environ["TEST_DATABASE_URL"]
    assert value.rsplit("/", 1)[-1].split("?", 1)[0] == "scanner_test"
    return value


def reset_test_schema() -> None:
    engine = create_engine(database_url_for_test())
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in (
            "integration_snapshots",
            "export_records",
            "scan_item_source_allocations",
            "scan_events",
            "scan_session_items",
            "scan_sessions",
            "cigarette_products",
            "user_sessions",
            "users",
        ):
            connection.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    engine.dispose()


def test_init_db_creates_current_tables_and_is_idempotent() -> None:
    reset_test_schema()
    initialize_database(database_url_for_test())
    engine = create_engine(database_url_for_test())
    now = datetime.now(UTC).replace(tzinfo=None)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users "
                "(username, password_hash, display_name, role, is_active, created_at, updated_at) "
                "VALUES ('keep-me', 'hash', '保留数据', 'VIEWER', 1, :now, :now)"
            ),
            {"now": now},
        )

    initialize_database(database_url_for_test())

    assert set(inspect(engine).get_table_names()) == {
        "users",
        "user_sessions",
        "cigarette_products",
        "scan_sessions",
        "scan_events",
        "scan_session_items",
        "scan_item_source_allocations",
        "export_records",
        "integration_snapshots",
    }
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    user_indexes = {index["name"] for index in inspect(engine).get_indexes("users")}
    assert "branch_code" in user_columns
    assert "idx_users_branch" in user_indexes
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM users")).scalar_one() == 1
    engine.dispose()
