from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Index, Numeric, SmallInteger, String, text
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

BIGINT_UNSIGNED = BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")
SMALLINT_UNSIGNED = SmallInteger().with_variant(mysql.SMALLINT(unsigned=True), "mysql")
MYSQL_DATETIME = mysql.DATETIME(fsp=6)
MYSQL_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class CigaretteProduct(Base):
    __tablename__ = "cigarette_products"
    __table_args__ = (
        Index("idx_products_pack_active", "pack_code", "is_active"),
        Index("idx_products_name", "brand", "standard_name"),
        MYSQL_TABLE_OPTIONS,
    )

    id: Mapped[int] = mapped_column(BIGINT_UNSIGNED, primary_key=True, autoincrement=True)
    carton_code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    pack_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    standard_name: Mapped[str] = mapped_column(String(200), nullable=False)
    carton_retail_price: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    sticks_per_pack: Mapped[int] = mapped_column(SMALLINT_UNSIGNED, nullable=False)
    packs_per_carton: Mapped[int] = mapped_column(SMALLINT_UNSIGNED, nullable=False)
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
