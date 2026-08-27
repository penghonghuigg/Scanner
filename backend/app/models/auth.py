from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

BIGINT_UNSIGNED = BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")
MYSQL_DATETIME = mysql.DATETIME(fsp=6)
MYSQL_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class Role(StrEnum):
    ADMIN = "ADMIN"
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'OPERATOR', 'VIEWER')",
            name="ck_users_role",
        ),
        CheckConstraint(
            "branch_code IS NULL OR branch_code IN "
            "('TIANDA', 'XIEBA', 'PANJI', 'SHOUXIAN', 'FENGTAI')",
            name="ck_users_branch",
        ),
        Index("idx_users_branch", "branch_code"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    branch_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
    )
    created_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (
        Index("idx_user_sessions_user_active", "user_id", "revoked_at", "expires_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(MYSQL_DATETIME, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(MYSQL_DATETIME, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
