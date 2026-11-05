from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import mysql

from app.db.base import Base
from app.models import finalization, scanning  # noqa: F401


def table_metadata(name: str):
    assert name in Base.metadata.tables, f"缺少数据表模型 {name}"
    return Base.metadata.tables[name]


def test_source_allocations_metadata_matches_stage_six_contract() -> None:
    allocations = table_metadata("scan_item_source_allocations")

    assert set(allocations.c.keys()) == {
        "id",
        "session_item_id",
        "source_type",
        "province_name",
        "city_name",
        "pack_count",
        "quantity_sticks",
        "source_key",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    }
    assert allocations.c.id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert allocations.c.session_item_id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert allocations.c.pack_count.type.dialect_impl(mysql.dialect()).unsigned is True
    assert allocations.c.quantity_sticks.type.dialect_impl(mysql.dialect()).unsigned is True
    assert allocations.c.province_name.nullable is True
    assert allocations.c.city_name.nullable is True
    assert {key.target_fullname for key in allocations.c.session_item_id.foreign_keys} == {
        "scan_session_items.id"
    }
    assert next(iter(allocations.c.session_item_id.foreign_keys)).ondelete == "CASCADE"
    assert {key.target_fullname for key in allocations.c.created_by.foreign_keys} == {
        "users.id"
    }
    assert {key.target_fullname for key in allocations.c.updated_by.foreign_keys} == {
        "users.id"
    }
    assert {
        constraint.name
        for constraint in allocations.constraints
        if isinstance(constraint, UniqueConstraint)
    } == {"uq_scan_item_source_allocations_item_key"}
    assert {
        constraint.name
        for constraint in allocations.constraints
        if isinstance(constraint, CheckConstraint)
    } == {
        "ck_scan_item_source_allocations_type",
        "ck_scan_item_source_allocations_quantity",
    }
    assert {index.name for index in allocations.indexes} == {
        "idx_scan_item_source_allocations_item"
    }


def test_export_records_metadata_matches_stage_seven_contract() -> None:
    exports = table_metadata("export_records")

    assert set(exports.c.keys()) == {
        "id",
        "session_id",
        "filename",
        "file_size",
        "file_sha256",
        "template_version",
        "generated_by",
        "created_at",
    }
    assert exports.c.id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert exports.c.session_id.type.dialect_impl(mysql.dialect()).unsigned is True
    assert exports.c.file_size.type.dialect_impl(mysql.dialect()).unsigned is True
    assert exports.c.file_sha256.type.length == 64
    assert {key.target_fullname for key in exports.c.session_id.foreign_keys} == {
        "scan_sessions.id"
    }
    assert {key.target_fullname for key in exports.c.generated_by.foreign_keys} == {
        "users.id"
    }
    assert {index.name for index in exports.indexes} == {
        "idx_export_records_session_created"
    }


def test_finalization_tables_use_mysql_persistent_options() -> None:
    for table_name in ("scan_item_source_allocations", "export_records"):
        table = table_metadata(table_name)
        assert table.dialect_options["mysql"]["engine"] == "InnoDB"
        assert table.dialect_options["mysql"]["charset"] == "utf8mb4"
        assert table.dialect_options["mysql"]["collate"] == "utf8mb4_0900_ai_ci"
