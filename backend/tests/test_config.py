import pytest
from pydantic import ValidationError


def test_production_rejects_insecure_session_cookie() -> None:
    try:
        from app.core.config import Settings
    except ModuleNotFoundError:
        pytest.fail("app.core.config 尚未实现")

    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="mysql+pymysql://scanner:secret@mysql/scanner",
            cookie_secure=False,
        )


def test_database_url_cannot_be_empty() -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(database_url="")
