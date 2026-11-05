from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.scanning import BIGINT_UNSIGNED, INT_UNSIGNED, MYSQL_DATETIME, MYSQL_TABLE_OPTIONS


class ScanItemSourceAllocation(Base):
    __tablename__ = "scan_item_source_allocations"
    __table_args__ = (
        CheckConstraint(
            "source_type IN "
            "('OUTSIDE_PROVINCE', 'UNKNOWN', 'LOCAL_HUAINAN', 'ANHUI_OTHER_CITY')",
            name="ck_scan_item_source_allocations_type",
        ),
        CheckConstraint(
            "pack_count > 0 AND quantity_sticks > 0",
            name="ck_scan_item_source_allocations_quantity",
        ),
        UniqueConstraint(
            "session_item_id",
            "source_key",
            name="uq_scan_item_source_allocations_item_key",
        ),
        Index("idx_scan_item_source_allocations_item", "session_item_id"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    session_item_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("scan_session_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    province_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    city_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pack_count: Mapped[int] = mapped_column(INT_UNSIGNED, nullable=False)
    quantity_sticks: Mapped[int] = mapped_column(INT_UNSIGNED, nullable=False)
    source_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    updated_by: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="RESTRICT"),
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


class ExportRecord(Base):
    __tablename__ = "export_records"
    __table_args__ = (
        Index("idx_export_records_session_created", "session_id", "created_at", "id"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("scan_sessions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(180), nullable=False)
    file_size: Mapped[int] = mapped_column(BIGINT_UNSIGNED, nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    template_version: Mapped[str] = mapped_column(String(20), nullable=False)
    generated_by: Mapped[int] = mapped_column(
        BIGINT_UNSIGNED,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        MYSQL_DATETIME,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
