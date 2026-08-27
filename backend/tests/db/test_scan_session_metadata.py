import pytest
from sqlalchemy.dialects import mysql

from app.db.base import Base


def scan_session_table():
    try:
        from app.models import scanning  # noqa: F401
    except ImportError:
        pytest.fail("app.models.scanning 尚未实现")
    return Base.metadata.tables["scan_sessions"]


def test_scan_session_metadata_matches_the_stage_four_contract() -> None:
    sessions = scan_session_table()

    assert set(sessions.c.keys()) == {
        "id",
        "session_no",
        "business_type",
        "filing_case_no",
        "location",
        "notes",
        "branch_code",
        "operator_id",
        "status",
        "completed_at",
        "created_at",
        "updated_at",
    }
    assert sessions.c.id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert sessions.c.session_no.type.length == 40
    assert sessions.c.session_no.unique is True
    assert sessions.c.business_type.type.length == 32
    assert sessions.c.filing_case_no.type.length == 100
    assert sessions.c.filing_case_no.nullable is True
    assert sessions.c.location.type.length == 200
    assert sessions.c.location.nullable is True
    assert sessions.c.notes.type.length == 500
    assert sessions.c.notes.nullable is True
    assert sessions.c.branch_code.type.length == 20
    assert sessions.c.branch_code.nullable is False
    assert sessions.c.operator_id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert {key.target_fullname for key in sessions.c.operator_id.foreign_keys} == {
        "users.id"
    }
    assert sessions.c.status.server_default.arg.text == "'DRAFT'"
    assert sessions.c.completed_at.nullable is True
    assert {constraint.name for constraint in sessions.constraints} >= {
        "ck_scan_sessions_business_type",
        "ck_scan_sessions_status",
    }
    assert {index.name for index in sessions.indexes} == {
        "idx_scan_sessions_branch_status_created",
        "idx_scan_sessions_operator_created",
    }


def test_scan_session_table_uses_mysql_persistent_options() -> None:
    sessions = scan_session_table()

    assert sessions.dialect_options["mysql"]["engine"] == "InnoDB"
    assert sessions.dialect_options["mysql"]["charset"] == "utf8mb4"
    assert sessions.dialect_options["mysql"]["collate"] == "utf8mb4_0900_ai_ci"
