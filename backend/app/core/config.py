from pathlib import Path
from typing import ClassVar, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    repository_env_file: ClassVar[Path] = Path(__file__).resolve().parents[3] / ".env"
    model_config = SettingsConfigDict(
        env_file=repository_env_file,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = Field(min_length=1)
    cookie_secure: bool = False
    session_ttl_hours: int = Field(default=8, ge=1, le=24)
    allowed_origins: str = "http://localhost:8080"
    jiandaoyun_create_url: str = ""
    jiandaoyun_app_id: str = ""
    jiandaoyun_entry_id: str = ""
    jiandaoyun_api_key: str = ""

    @model_validator(mode="after")
    def require_secure_production_cookie(self) -> "Settings":
        if self.app_env == "production" and not self.cookie_secure:
            raise ValueError("生产环境必须启用 Secure Cookie")
        return self

    @property
    def allowed_origin_set(self) -> frozenset[str]:
        return frozenset(
            origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()
        )
