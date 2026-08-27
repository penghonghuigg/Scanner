import os
import re
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def main() -> int:
    load_dotenv(REPOSITORY_ROOT / ".env")
    test_url_value = os.environ.get("TEST_DATABASE_URL", "")
    root_password = os.environ.get("MYSQL_ROOT_PASSWORD", "")
    database_user = os.environ.get("MYSQL_USER", "")

    test_url = make_url(test_url_value)
    if test_url.database != "scanner_test":
        raise SystemExit("TEST_DATABASE_URL 只允许指向 scanner_test")
    if not root_password:
        raise SystemExit("MYSQL_ROOT_PASSWORD 未配置")
    if not SAFE_IDENTIFIER.fullmatch(database_user):
        raise SystemExit("MYSQL_USER 只能包含字母、数字和下划线")

    connection = pymysql.connect(
        host=test_url.host or "127.0.0.1",
        port=test_url.port or 3306,
        user="root",
        password=root_password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "CREATE DATABASE IF NOT EXISTS scanner_test "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
            cursor.execute(
                f"GRANT ALL PRIVILEGES ON scanner_test.* TO '{database_user}'@'%'"
            )
    finally:
        connection.close()

    print("scanner_test 已就绪")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
