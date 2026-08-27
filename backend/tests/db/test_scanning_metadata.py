from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import mysql

from app.db.base import Base
from app.models import scanning  # noqa: F401


def test_scan_events_metadata_matches_stage_five_contract() -> None:
    events = Base.metadata.tables["scan_events"]

    assert set(events.c.keys()) == {
        "id",
        "request_id",
        "session_id",
        "event_type",
        "result",
        "raw_code",
        "product_id",
        "unit_type",
        "delta_sticks",
        "source_event_id",
        "reason",
        "candidate_snapshot",
        "product_snapshot",
        "operator_id",
        "created_at",
    }
    assert events.c.id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert events.c.request_id.type.length == 36
    assert events.c.session_id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert events.c.event_type.type.length == 24
    assert events.c.result.type.length == 24
    assert events.c.raw_code.type.length == 64
    assert events.c.product_id.nullable is True
    assert events.c.unit_type.nullable is True
    assert events.c.source_event_id.nullable is True
    assert isinstance(
        events.c.candidate_snapshot.type.dialect_impl(mysql.dialect()), mysql.JSON
    )
    assert isinstance(
        events.c.product_snapshot.type.dialect_impl(mysql.dialect()), mysql.JSON
    )
    assert {key.target_fullname for key in events.c.session_id.foreign_keys} == {
        "scan_sessions.id"
    }
    assert {key.target_fullname for key in events.c.product_id.foreign_keys} == {
        "cigarette_products.id"
    }
    assert {key.target_fullname for key in events.c.source_event_id.foreign_keys} == {
        "scan_events.id"
    }
    assert {key.target_fullname for key in events.c.operator_id.foreign_keys} == {
        "users.id"
    }
    assert {
        constraint.name
        for constraint in events.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_scan_events_request_id", "uq_scan_events_source_event"}
    assert {
        constraint.name
        for constraint in events.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_scan_events_event_type",
        "ck_scan_events_result",
        "ck_scan_events_unit_type",
    }
    assert {index.name for index in events.indexes} == {
        "idx_scan_events_session_created",
        "idx_scan_events_session_result",
    }


def test_scan_session_items_metadata_matches_stage_five_contract() -> None:
    items = Base.metadata.tables["scan_session_items"]

    assert set(items.c.keys()) == {
        "id",
        "session_id",
        "product_id",
        "carton_count",
        "pack_count",
        "manual_delta_sticks",
        "total_sticks",
        "product_snapshot",
        "updated_at",
    }
    assert items.c.id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert items.c.carton_count.type.dialect_impl(mysql.dialect()).unsigned is True
    assert items.c.pack_count.type.dialect_impl(mysql.dialect()).unsigned is True
    assert items.c.total_sticks.type.dialect_impl(mysql.dialect()).unsigned is True
    assert items.c.carton_count.server_default.arg.text == "0"
    assert items.c.pack_count.server_default.arg.text == "0"
    assert items.c.manual_delta_sticks.server_default.arg.text == "0"
    assert items.c.total_sticks.server_default.arg.text == "0"
    assert isinstance(
        items.c.product_snapshot.type.dialect_impl(mysql.dialect()), mysql.JSON
    )
    assert {key.target_fullname for key in items.c.session_id.foreign_keys} == {
        "scan_sessions.id"
    }
    assert {key.target_fullname for key in items.c.product_id.foreign_keys} == {
        "cigarette_products.id"
    }
    assert {
        constraint.name
        for constraint in items.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_scan_session_items_session_product"}
    assert {
        constraint.name
        for constraint in items.constraints
        if isinstance(constraint, CheckConstraint)
    } == {"ck_scan_session_items_quantities"}
    assert {index.name for index in items.indexes} == {
        "idx_scan_items_session_updated"
    }


def test_stage_five_tables_use_mysql_persistent_options() -> None:
    for table_name in ("scan_events", "scan_session_items"):
        table = Base.metadata.tables[table_name]
        assert table.dialect_options["mysql"]["engine"] == "InnoDB"
        assert table.dialect_options["mysql"]["charset"] == "utf8mb4"
        assert table.dialect_options["mysql"]["collate"] == "utf8mb4_0900_ai_ci"
