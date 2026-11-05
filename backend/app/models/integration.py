from datetime import datetime

from sqlalchemy import (
    CHAR,
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.scanning import (
    BIGINT_UNSIGNED,
    INT_UNSIGNED,
    MYSQL_DATETIME,
    MYSQL_TABLE_OPTIONS,
)


class IntegrationSnapshot(Base):
    __tablename__ = "integration_snapshots"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'SUCCEEDED', 'FAILED', 'UNCERTAIN')",
            name="ck_integration_snapshots_status",
        ),
        UniqueConstraint("session_id", name="uq_integration_snapshots_session"),
        Index(
            "idx_integration_snapshots_status_updated",
            "status",
            "updated_at",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "scan_sessions.id",
            name="fk_integration_snapshots_session",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    external_data_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        INT_UNSIGNED,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "users.id",
            name="fk_integration_snapshots_created_by",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    last_attempted_by: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey(
            "users.id",
            name="fk_integration_snapshots_last_attempted_by",
            ondelete="RESTRICT",
        ),
        nullable=False,
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
    succeeded_at: Mapped[datetime | None] = mapped_column(MYSQL_DATETIME, nullable=True)
