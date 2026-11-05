import importlib
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import mysql

from app.db.base import Base

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CREATE_SQL = REPOSITORY_ROOT / "backend/scripts/sql/08_create_integration_snapshots.sql"


def integration_snapshots_table():
    try:
        importlib.import_module("app.models.integration")
    except ModuleNotFoundError as exc:
        pytest.fail(f"缺少阶段 8 集成快照模型：{exc}")

    assert "integration_snapshots" in Base.metadata.tables
    return Base.metadata.tables["integration_snapshots"]


def test_integration_snapshot_metadata_matches_stage_eight_contract() -> None:
    snapshots = integration_snapshots_table()

    assert set(snapshots.c.keys()) == {
        "id",
        "session_id",
        "payload_json",
        "payload_sha256",
        "status",
        "external_data_id",
        "attempt_count",
        "last_error_code",
        "last_error_message",
        "created_by",
        "last_attempted_by",
        "created_at",
        "updated_at",
        "succeeded_at",
    }
    for column_name in (
        "id",
        "session_id",
        "attempt_count",
        "created_by",
        "last_attempted_by",
    ):
        column_type = snapshots.c[column_name].type.dialect_impl(mysql.dialect())
        assert column_type.unsigned is True

    assert snapshots.c.payload_json.nullable is False
    assert snapshots.c.payload_sha256.type.length == 64
    assert snapshots.c.external_data_id.nullable is True
    assert snapshots.c.attempt_count.nullable is False
    assert str(snapshots.c.attempt_count.server_default.arg) == "0"
    assert snapshots.c.succeeded_at.nullable is True


def test_integration_snapshot_constraints_and_indexes_are_named() -> None:
    snapshots = integration_snapshots_table()

    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in snapshots.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique_constraints == {
        "uq_integration_snapshots_session": ("session_id",),
    }

    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in snapshots.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert set(checks) == {"ck_integration_snapshots_status"}
    for status in ("PENDING", "SUCCEEDED", "FAILED", "UNCERTAIN"):
        assert status in checks["ck_integration_snapshots_status"]

    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in snapshots.indexes
    }
    assert indexes == {
        "idx_integration_snapshots_status_updated": ("status", "updated_at"),
    }


def test_integration_snapshot_foreign_keys_and_mysql_options_match_contract() -> None:
    snapshots = integration_snapshots_table()

    expected_foreign_keys = {
        "session_id": (
            "fk_integration_snapshots_session",
            "scan_sessions.id",
        ),
        "created_by": (
            "fk_integration_snapshots_created_by",
            "users.id",
        ),
        "last_attempted_by": (
            "fk_integration_snapshots_last_attempted_by",
            "users.id",
        ),
    }
    for column_name, (constraint_name, target) in expected_foreign_keys.items():
        foreign_key = next(iter(snapshots.c[column_name].foreign_keys))
        assert foreign_key.constraint.name == constraint_name
        assert foreign_key.target_fullname == target
        assert foreign_key.ondelete == "RESTRICT"

    assert snapshots.dialect_options["mysql"]["engine"] == "InnoDB"
    assert snapshots.dialect_options["mysql"]["charset"] == "utf8mb4"
    assert snapshots.dialect_options["mysql"]["collate"] == "utf8mb4_0900_ai_ci"


def test_create_sql_is_single_target_and_matches_metadata_names() -> None:
    snapshots = integration_snapshots_table()
    sql = CREATE_SQL.read_text(encoding="utf-8")
    normalized_sql = sql.upper()

    assert normalized_sql.count("CREATE TABLE") == 1
    assert "CREATE TABLE `INTEGRATION_SNAPSHOTS`" in normalized_sql
    assert "DROP TABLE" not in normalized_sql
    assert "ALTER TABLE" not in normalized_sql
    for column in snapshots.c:
        assert f"`{column.name}`" in sql
    for constraint in snapshots.constraints:
        if constraint.name:
            assert f"`{constraint.name}`" in sql
    for index in snapshots.indexes:
        assert f"`{index.name}`" in sql
    assert "ENGINE=InnoDB" in sql
    assert "DEFAULT CHARSET=utf8mb4" in sql
    assert "COLLATE=utf8mb4_0900_ai_ci" in sql
