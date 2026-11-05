import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.catalog import CigaretteProduct

CODE_PATTERN = re.compile(r"\d{6,64}")
MONEY_UNIT = Decimal("0.01")


class CatalogValidationError(ValueError):
    pass


class CartonCodeExistsError(ValueError):
    pass


class PackCodeConflictError(ValueError):
    pass


class ProductNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class ProductListResult:
    items: list[CigaretteProduct]
    total: int
    total_count: int
    active_count: int
    inactive_count: int
    ambiguous_count: int


@dataclass(frozen=True)
class ProductOptionListResult:
    items: list[CigaretteProduct]
    total: int


def calculate_pack_price(
    carton_retail_price: Decimal | None,
    packs_per_carton: int,
) -> Decimal | None:
    if carton_retail_price is None:
        return None
    return (carton_retail_price / packs_per_carton).quantize(
        MONEY_UNIT,
        rounding=ROUND_HALF_UP,
    )


def calculate_sticks_per_carton(sticks_per_pack: int, packs_per_carton: int) -> int:
    return sticks_per_pack * packs_per_carton


def normalize_code(value: str | None, *, required: bool) -> str | None:
    normalized = value.strip() if value is not None else ""
    if not normalized:
        if required:
            raise CatalogValidationError("条码不能为空")
        return None
    if not CODE_PATTERN.fullmatch(normalized):
        raise CatalogValidationError("编码必须为 6 至 64 位数字")
    return normalized


def validate_product_values(
    *,
    brand: str,
    standard_name: str,
    carton_retail_price: Decimal | None,
    sticks_per_pack: int,
    packs_per_carton: int,
) -> tuple[str, str]:
    normalized_brand = brand.strip()
    normalized_name = standard_name.strip()
    if not normalized_brand or not normalized_name:
        raise CatalogValidationError("品牌和品规名称不能为空")
    if carton_retail_price is not None and carton_retail_price < 0:
        raise CatalogValidationError("每条零售价不能小于零")
    if sticks_per_pack <= 0 or packs_per_carton <= 0:
        raise CatalogValidationError("包装数量必须为正整数")
    return normalized_brand, normalized_name


def ensure_code_relationships(
    session: Session,
    *,
    carton_code: str,
    pack_code: str | None,
    exclude_product_id: int | None = None,
) -> None:
    excluded = (
        CigaretteProduct.id != exclude_product_id
        if exclude_product_id is not None
        else True
    )
    if session.scalar(
        select(CigaretteProduct.id).where(
            CigaretteProduct.carton_code == carton_code,
            excluded,
        )
    ) is not None:
        raise CartonCodeExistsError("条码已属于其他品规版本")
    if session.scalar(
        select(CigaretteProduct.id).where(
            CigaretteProduct.pack_code == carton_code,
            excluded,
        )
    ) is not None:
        raise PackCodeConflictError("条码与现有包码冲突")
    if pack_code is not None and session.scalar(
        select(CigaretteProduct.id).where(
            CigaretteProduct.carton_code == pack_code,
            excluded,
        )
    ) is not None:
        raise PackCodeConflictError("包码与现有条码冲突")
    if pack_code == carton_code:
        raise PackCodeConflictError("包码不能与条码相同")


def create_product(
    session: Session,
    *,
    carton_code: str,
    pack_code: str | None,
    brand: str,
    standard_name: str,
    carton_retail_price: Decimal | None,
    sticks_per_pack: int,
    packs_per_carton: int,
    is_active: bool = True,
) -> CigaretteProduct:
    normalized_carton = normalize_code(carton_code, required=True)
    assert normalized_carton is not None
    normalized_pack = normalize_code(pack_code, required=False)
    normalized_brand, normalized_name = validate_product_values(
        brand=brand,
        standard_name=standard_name,
        carton_retail_price=carton_retail_price,
        sticks_per_pack=sticks_per_pack,
        packs_per_carton=packs_per_carton,
    )
    ensure_code_relationships(
        session,
        carton_code=normalized_carton,
        pack_code=normalized_pack,
    )
    product = CigaretteProduct(
        carton_code=normalized_carton,
        pack_code=normalized_pack,
        brand=normalized_brand,
        standard_name=normalized_name,
        carton_retail_price=carton_retail_price,
        sticks_per_pack=sticks_per_pack,
        packs_per_carton=packs_per_carton,
        is_active=is_active,
    )
    session.add(product)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CartonCodeExistsError("条码已属于其他品规版本") from exc
    session.refresh(product)
    return product


def is_pack_code_ambiguous(session: Session, pack_code: str | None) -> bool:
    if not pack_code:
        return False
    count = session.scalar(
        select(func.count(CigaretteProduct.id)).where(
            CigaretteProduct.pack_code == pack_code,
            CigaretteProduct.is_active.is_(True),
        )
    )
    return (count or 0) > 1


def update_product(
    session: Session,
    product_id: int,
    **values: object,
) -> CigaretteProduct:
    product = session.get(CigaretteProduct, product_id)
    if product is None:
        raise ProductNotFoundError("品规版本不存在")
    merged = {
        "carton_code": values.get("carton_code", product.carton_code),
        "pack_code": values.get("pack_code", product.pack_code),
        "brand": values.get("brand", product.brand),
        "standard_name": values.get("standard_name", product.standard_name),
        "carton_retail_price": values.get(
            "carton_retail_price", product.carton_retail_price
        ),
        "sticks_per_pack": values.get("sticks_per_pack", product.sticks_per_pack),
        "packs_per_carton": values.get("packs_per_carton", product.packs_per_carton),
        "is_active": values.get("is_active", product.is_active),
    }
    normalized_carton = normalize_code(str(merged["carton_code"]), required=True)
    assert normalized_carton is not None
    raw_pack = merged["pack_code"]
    normalized_pack = normalize_code(
        str(raw_pack) if raw_pack is not None else None,
        required=False,
    )
    normalized_brand, normalized_name = validate_product_values(
        brand=str(merged["brand"]),
        standard_name=str(merged["standard_name"]),
        carton_retail_price=merged["carton_retail_price"],  # type: ignore[arg-type]
        sticks_per_pack=int(merged["sticks_per_pack"]),
        packs_per_carton=int(merged["packs_per_carton"]),
    )
    ensure_code_relationships(
        session,
        carton_code=normalized_carton,
        pack_code=normalized_pack,
        exclude_product_id=product.id,
    )
    product.carton_code = normalized_carton
    product.pack_code = normalized_pack
    product.brand = normalized_brand
    product.standard_name = normalized_name
    product.carton_retail_price = merged["carton_retail_price"]  # type: ignore[assignment]
    product.sticks_per_pack = int(merged["sticks_per_pack"])
    product.packs_per_carton = int(merged["packs_per_carton"])
    product.is_active = bool(merged["is_active"])
    product.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.commit()
    session.refresh(product)
    return product


def search_filter(query: str):
    pattern = f"%{query.strip()}%"
    return or_(
        CigaretteProduct.brand.like(pattern),
        CigaretteProduct.standard_name.like(pattern),
        CigaretteProduct.carton_code.like(pattern),
        CigaretteProduct.pack_code.like(pattern),
    )


def list_active_product_options(
    session: Session,
    *,
    query: str,
    page: int = 1,
    page_size: int = 20,
) -> ProductOptionListResult:
    normalized = query.strip()
    if not normalized:
        return ProductOptionListResult(items=[], total=0)
    pattern = f"%{normalized}%"
    filters = (
        CigaretteProduct.is_active.is_(True),
        or_(
            CigaretteProduct.standard_name.like(pattern),
            CigaretteProduct.carton_code.like(pattern),
        ),
    )
    total = session.scalar(select(func.count(CigaretteProduct.id)).where(*filters)) or 0
    items = list(
        session.scalars(
            select(CigaretteProduct)
            .where(*filters)
            .order_by(CigaretteProduct.standard_name, CigaretteProduct.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return ProductOptionListResult(items=items, total=int(total))


def list_products(
    session: Session,
    *,
    query: str = "",
    is_active: bool | None = None,
    ambiguous: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ProductListResult:
    ambiguous_codes = (
        select(CigaretteProduct.pack_code)
        .where(
            CigaretteProduct.pack_code.is_not(None),
            CigaretteProduct.is_active.is_(True),
        )
        .group_by(CigaretteProduct.pack_code)
        .having(func.count(CigaretteProduct.id) > 1)
    )
    filters = []
    if query.strip():
        filters.append(search_filter(query))
    if is_active is not None:
        filters.append(CigaretteProduct.is_active.is_(is_active))
    if ambiguous is True:
        filters.append(CigaretteProduct.pack_code.in_(ambiguous_codes))
    elif ambiguous is False:
        filters.append(
            or_(
                CigaretteProduct.pack_code.is_(None),
                CigaretteProduct.pack_code.not_in(ambiguous_codes),
            )
        )

    total = session.scalar(select(func.count(CigaretteProduct.id)).where(*filters)) or 0
    items = list(
        session.scalars(
            select(CigaretteProduct)
            .where(*filters)
            .order_by(CigaretteProduct.updated_at.desc(), CigaretteProduct.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    total_count = session.scalar(select(func.count(CigaretteProduct.id))) or 0
    active_count = (
        session.scalar(
            select(func.count(CigaretteProduct.id)).where(
                CigaretteProduct.is_active.is_(True)
            )
        )
        or 0
    )
    ambiguous_count = (
        session.scalar(
            select(func.count(CigaretteProduct.id)).where(
                CigaretteProduct.pack_code.in_(ambiguous_codes),
                CigaretteProduct.is_active.is_(True),
            )
        )
        or 0
    )
    return ProductListResult(
        items=items,
        total=total,
        total_count=total_count,
        active_count=active_count,
        inactive_count=total_count - active_count,
        ambiguous_count=ambiguous_count,
    )
