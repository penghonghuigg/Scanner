from dataclasses import dataclass

from sqlalchemy import Engine, create_engine, inspect, text

from app.db.base import Base
from app.models import auth, catalog, finalization, integration, scanning  # noqa: F401


class SchemaMismatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class SchemaReport:
    tables: tuple[str, ...]


def validate_database_schema(engine: Engine) -> SchemaReport:
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables)
    differences: list[str] = []

    for table_name in sorted(expected_tables - actual_tables):
        differences.append(f"缺少数据表 {table_name}")

    for table_name in sorted(expected_tables & actual_tables):
        expected_columns = set(Base.metadata.tables[table_name].c.keys())
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}
        for column_name in sorted(expected_columns - actual_columns):
            differences.append(f"缺少字段 {table_name}.{column_name}")

        expected_indexes = {index.name for index in Base.metadata.tables[table_name].indexes}
        actual_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        for index_name in sorted(expected_indexes - actual_indexes):
            differences.append(f"缺少索引 {table_name}.{index_name}")

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT TABLE_NAME, ENGINE, TABLE_COLLATION "
                "FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).mappings()
        table_options = {row["TABLE_NAME"]: row for row in rows}

    for table_name in sorted(expected_tables & actual_tables):
        options = table_options[table_name]
        if options["ENGINE"] != "InnoDB":
            differences.append(f"表引擎不一致 {table_name}.ENGINE")
        if options["TABLE_COLLATION"] != "utf8mb4_0900_ai_ci":
            differences.append(f"排序规则不一致 {table_name}.TABLE_COLLATION")

    if differences:
        raise SchemaMismatchError("；".join(differences))

    return SchemaReport(tables=tuple(sorted(expected_tables)))


def initialize_database(database_url: str) -> SchemaReport:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        Base.metadata.create_all(engine)
        return validate_database_schema(engine)
    finally:
        engine.dispose()
