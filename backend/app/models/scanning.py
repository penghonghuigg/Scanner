from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

BIGINT_UNSIGNED = BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")
INT_UNSIGNED = Integer().with_variant(mysql.INTEGER(unsigned=True), "mysql")
MYSQL_DATETIME = mysql.DATETIME(fsp=6)
MYSQL_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class ScanSession(Base):
    __tablename__ = "scan_sessions"
    __table_args__ = (
        CheckConstraint(
            "business_type IN "
            "('MARKET_INSPECTION', 'DELIVERY_CHANNEL', 'SPECIAL_TRANSPORT', 'OTHER')",
            name="ck_scan_sessions_business_type",
        ),
        CheckConstraint(
            "branch_code IN ('TIANDA', 'XIEBA', 'PANJI', 'SHOUXIAN', 'FENGTAI')",
            name="ck_scan_sessions_branch",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'COMPLETED')",
            name="ck_scan_sessions_status",
        ),
        Index(
            "idx_scan_sessions_branch_status_created",
            "branch_code",
            "status",
            "created_at",
        ),
        Index(
            "idx_scan_sessions_operator_created",
            "operator_id",
            "created_at",
        ),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    session_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    business_type: Mapped[str] = mapped_column(String(32), nullable=False)
    filing_case_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    branch_code: Mapped[str] = mapped_column(String(20), nullable=False)
    operator_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="DRAFT",
        server_default=text("'DRAFT'"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(MYSQL_DATETIME, nullable=True)
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


class ScanEvent(Base):
    __tablename__ = "scan_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('SCAN', 'RESOLVE', 'ADJUST')",
            name="ck_scan_events_event_type",
        ),
        CheckConstraint(
            "result IN ('SUCCESS', 'UNKNOWN', 'AMBIGUOUS')",
            name="ck_scan_events_result",
        ),
        CheckConstraint(
            "unit_type IS NULL OR unit_type IN ('CARTON', 'PACK', 'STICK')",
            name="ck_scan_events_unit_type",
        ),
        UniqueConstraint("request_id", name="uq_scan_events_request_id"),
        UniqueConstraint("source_event_id", name="uq_scan_events_source_event"),
        Index("idx_scan_events_session_created", "session_id", "created_at", "id"),
        Index("idx_scan_events_session_result", "session_id", "result", "created_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False)
    session_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("scan_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    result: Mapped[str] = mapped_column(String(24), nullable=False)
    raw_code: Mapped[str] = mapped_column(String(64), nullable=False)
    product_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("cigarette_products.id", ondelete="RESTRICT"),
        nullable=True,
    )
    unit_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    delta_sticks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_event_id: Mapped[int | None] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("scan_events.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    candidate_snapshot: Mapped[list[dict[str, object]] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    product_snapshot: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    operator_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )


class ScanSessionItem(Base):
    __tablename__ = "scan_session_items"
    __table_args__ = (
        CheckConstraint(
            "carton_count >= 0 AND pack_count >= 0 AND total_sticks >= 0",
            name="ck_scan_session_items_quantities",
        ),
        UniqueConstraint(
            "session_id",
            "product_id",
            name="uq_scan_session_items_session_product",
        ),
        Index("idx_scan_items_session_updated", "session_id", "updated_at"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("scan_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("cigarette_products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    carton_count: Mapped[int] = mapped_column(
        INT_UNSIGNED,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    pack_count: Mapped[int] = mapped_column(
        INT_UNSIGNED,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    manual_delta_sticks: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    total_sticks: Mapped[int] = mapped_column(
        INT_UNSIGNED,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    product_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
