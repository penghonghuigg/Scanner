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


def test_production_allows_insecure_cookie_only_with_explicit_http_override() -> None:
    from app.core.config import Settings

    settings = Settings(
        app_env="production",
        database_url="mysql+pymysql://scanner:secret@mysql/scanner",
        cookie_secure=False,
        allow_insecure_http=True,
        allowed_origins="http://203.0.113.10",
    )

    assert settings.cookie_secure is False
    assert settings.allow_insecure_http is True
    assert settings.allowed_origin_set == frozenset({"http://203.0.113.10"})


def test_database_url_cannot_be_empty() -> None:
    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(database_url="")


def test_production_settings_accept_secure_https_origin() -> None:
    from app.core.config import Settings

    settings = Settings(
        app_env="production",
        database_url="mysql+pymysql://scanner:secret@scanner-mysql/scanner",
        cookie_secure=True,
        allowed_origins="https://203.0.113.10",
    )

    assert settings.cookie_secure is True
    assert settings.allowed_origin_set == frozenset({"https://203.0.113.10"})
