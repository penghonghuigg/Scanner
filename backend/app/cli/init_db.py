from app.core.config import Settings
from app.db.schema import SchemaMismatchError, initialize_database


def main() -> int:
    settings = Settings()
    try:
        report = initialize_database(settings.database_url)
    except SchemaMismatchError as exc:
        print(f"数据库结构校验失败：{exc}")
        return 1

    print(f"数据库初始化完成：{', '.join(report.tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
