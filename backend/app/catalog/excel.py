from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Literal

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog.service import CODE_PATTERN
from app.models.catalog import CigaretteProduct

IMPORT_HEADERS = ("条码", "品规名称", "包码", "品牌", "零售价格", "包数量", "条数量")
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_DATA_ROWS = 10_000


class ImportFileInvalidError(ValueError):
    pass


@dataclass(frozen=True)
class ImportIssue:
    row_number: int
    level: Literal["ERROR", "WARNING"]
    field: str
    code: str
    message: str
    carton_code: str
    standard_name: str


@dataclass(frozen=True)
class ImportRow:
    row_number: int
    carton_code: str
    pack_code: str | None
    brand: str
    standard_name: str
    carton_retail_price: Decimal | None
    sticks_per_pack: int
    packs_per_carton: int


@dataclass(frozen=True)
class ParsedImport:
    total_rows: int
    rows: list[ImportRow]
    issues: list[ImportIssue]


@dataclass(frozen=True)
class ImportResult:
    total_rows: int
    created_count: int
    updated_count: int
    skipped_count: int
    warning_count: int
    issues: list[ImportIssue]


def build_import_template() -> bytes:
    workbook = Workbook()
    data_sheet = workbook.active
    data_sheet.title = "品规导入"
    data_sheet.append(IMPORT_HEADERS)
    data_sheet.append(
        (
            "6901028000011",
            "示例品牌（经典）",
            "6901028000028",
            "示例品牌",
            100,
            20,
            200,
        )
    )
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in data_sheet[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center")
    data_sheet["A2"].number_format = "@"
    data_sheet["C2"].number_format = "@"
    data_sheet.freeze_panes = "A2"
    for column, width in {"A": 22, "B": 30, "C": 22, "D": 18, "E": 14, "F": 12, "G": 12}.items():
        data_sheet.column_dimensions[column].width = width

    instructions = workbook.create_sheet("填写说明")
    instructions.append(("字段", "是否必填", "填写规则"))
    instruction_rows = (
        ("条码", "是", "6～64 位数字，每个品规版本唯一，按文本填写"),
        ("品规名称", "是", "同名但条码不同表示不同版本"),
        ("包码", "否", "6～64 位数字；空或 -1 表示无包码；允许重复"),
        ("品牌", "是", "卷烟品牌"),
        ("零售价格", "否", "每条参考零售价；空或 -1 表示未知"),
        ("包数量", "是", "每包支数；无包码的单一包装可填 -1"),
        ("条数量", "是", "每条总支数，必须能被包数量整除"),
    )
    for row in instruction_rows:
        instructions.append(row)
    for cell in instructions[1]:
        cell.fill = header_fill
        cell.font = Font(color="FFFFFF", bold=True)
    instructions.column_dimensions["A"].width = 18
    instructions.column_dimensions["B"].width = 12
    instructions.column_dimensions["C"].width = 64
    instructions.freeze_panes = "A2"

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def parse_positive_integer(value: object) -> int | None:
    text = cell_text(value)
    try:
        decimal_value = Decimal(text)
    except InvalidOperation:
        return None
    if decimal_value <= 0 or decimal_value != decimal_value.to_integral_value():
        return None
    return int(decimal_value)


def parse_price(value: object) -> Decimal | None:
    text = cell_text(value)
    if text in {"", "-1"}:
        return None
    try:
        price = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("每条零售价必须为非负数字") from exc
    if price < 0:
        raise ValueError("每条零售价必须为非负数字")
    return price.quantize(Decimal("0.01"))


def issue_for(
    row_number: int,
    *,
    level: Literal["ERROR", "WARNING"],
    field: str,
    code: str,
    message: str,
    carton_code: str,
    standard_name: str,
) -> ImportIssue:
    return ImportIssue(
        row_number=row_number,
        level=level,
        field=field,
        code=code,
        message=message,
        carton_code=carton_code,
        standard_name=standard_name,
    )


def parse_row(
    row_number: int,
    values: tuple[object, ...],
) -> tuple[ImportRow | None, ImportIssue | None]:
    carton_code, standard_name, pack_code, brand, price, pack_quantity, carton_quantity = (
        cell_text(value) for value in values
    )
    if not CODE_PATTERN.fullmatch(carton_code):
        return None, issue_for(
            row_number,
            level="ERROR",
            field="条码",
            code="CARTON_CODE_INVALID",
            message="条码必须为 6 至 64 位数字",
            carton_code=carton_code,
            standard_name=standard_name,
        )
    if not standard_name or not brand:
        return None, issue_for(
            row_number,
            level="ERROR",
            field="品规名称/品牌",
            code="PRODUCT_REQUIRED_FIELD_MISSING",
            message="品规名称和品牌不能为空",
            carton_code=carton_code,
            standard_name=standard_name,
        )
    normalized_pack = None if pack_code in {"", "-1"} else pack_code
    if normalized_pack is not None and not CODE_PATTERN.fullmatch(normalized_pack):
        return None, issue_for(
            row_number,
            level="ERROR",
            field="包码",
            code="PACK_CODE_INVALID",
            message="包码必须为 6 至 64 位数字",
            carton_code=carton_code,
            standard_name=standard_name,
        )
    try:
        normalized_price = parse_price(price)
    except ValueError as exc:
        return None, issue_for(
            row_number,
            level="ERROR",
            field="零售价格",
            code="PRICE_INVALID",
            message=str(exc),
            carton_code=carton_code,
            standard_name=standard_name,
        )
    carton_sticks = parse_positive_integer(carton_quantity)
    if carton_sticks is None:
        return None, issue_for(
            row_number,
            level="ERROR",
            field="条数量",
            code="PACKAGE_QUANTITY_INVALID",
            message="条数量必须为正整数",
            carton_code=carton_code,
            standard_name=standard_name,
        )
    if pack_quantity == "-1":
        if normalized_pack is not None:
            return None, issue_for(
                row_number,
                level="ERROR",
                field="包数量",
                code="PACKAGE_QUANTITY_INVALID",
                message="存在包码时包数量不能为 -1",
                carton_code=carton_code,
                standard_name=standard_name,
            )
        sticks_per_pack = carton_sticks
        packs_per_carton = 1
    else:
        sticks_per_pack = parse_positive_integer(pack_quantity)
        if sticks_per_pack is None:
            return None, issue_for(
                row_number,
                level="ERROR",
                field="包数量",
                code="PACKAGE_QUANTITY_INVALID",
                message="包数量必须为正整数",
                carton_code=carton_code,
                standard_name=standard_name,
            )
        if carton_sticks % sticks_per_pack != 0:
            return None, issue_for(
                row_number,
                level="ERROR",
                field="包数量/条数量",
                code="PACKAGE_CONVERSION_INVALID",
                message="条数量必须能被包数量整除",
                carton_code=carton_code,
                standard_name=standard_name,
            )
        packs_per_carton = carton_sticks // sticks_per_pack
    return (
        ImportRow(
            row_number=row_number,
            carton_code=carton_code,
            pack_code=normalized_pack,
            brand=brand,
            standard_name=standard_name,
            carton_retail_price=normalized_price,
            sticks_per_pack=sticks_per_pack,
            packs_per_carton=packs_per_carton,
        ),
        None,
    )


def parse_import_workbook(content: bytes) -> ParsedImport:
    if not content or len(content) > MAX_FILE_SIZE:
        raise ImportFileInvalidError("Excel 文件为空或超过 10 MB")
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise ImportFileInvalidError("无法读取 Excel 文件") from exc
    sheet = workbook.active
    headers = tuple(cell_text(cell.value) for cell in sheet[1])
    if headers != IMPORT_HEADERS:
        raise ImportFileInvalidError("Excel 表头与导入模板不一致")
    raw_rows = [
        (row_number, tuple(cell.value for cell in cells))
        for row_number, cells in enumerate(sheet.iter_rows(min_row=2), start=2)
        if any(cell.value is not None and cell_text(cell.value) for cell in cells)
    ]
    if len(raw_rows) > MAX_DATA_ROWS:
        raise ImportFileInvalidError("Excel 数据行不能超过 10000 行")

    rows: list[ImportRow] = []
    issues: list[ImportIssue] = []
    carton_counts = Counter(cell_text(values[0]) for _, values in raw_rows)
    for row_number, values in raw_rows:
        parsed, issue = parse_row(row_number, values)
        if issue is not None:
            issues.append(issue)
            continue
        assert parsed is not None
        if carton_counts[parsed.carton_code] > 1:
            issues.append(
                issue_for(
                    row_number,
                    level="ERROR",
                    field="条码",
                    code="CARTON_CODE_DUPLICATE",
                    message="同一文件中条码重复",
                    carton_code=parsed.carton_code,
                    standard_name=parsed.standard_name,
                )
            )
            continue
        rows.append(parsed)
    issues.sort(key=lambda item: (item.row_number, item.level, item.code))
    return ParsedImport(total_rows=len(raw_rows), rows=rows, issues=issues)


def import_products_from_workbook(session: Session, content: bytes) -> ImportResult:
    parsed = parse_import_workbook(content)
    issues = list(parsed.issues)
    file_carton_codes = {row.carton_code for row in parsed.rows}
    database_carton_codes = set(session.scalars(select(CigaretteProduct.carton_code)))
    all_carton_codes = file_carton_codes | database_carton_codes
    created_count = 0
    updated_count = 0
    now = datetime.now(UTC).replace(tzinfo=None)

    try:
        for row in parsed.rows:
            pack_code = row.pack_code
            if pack_code is not None and pack_code in all_carton_codes:
                issues.append(
                    issue_for(
                        row.row_number,
                        level="WARNING",
                        field="包码",
                        code="PACK_CODE_CONFLICT_CLEARED",
                        message="包码与条码冲突，已清空包码",
                        carton_code=row.carton_code,
                        standard_name=row.standard_name,
                    )
                )
                pack_code = None

            conflicting_existing_packs = list(
                session.scalars(
                    select(CigaretteProduct).where(
                        CigaretteProduct.pack_code == row.carton_code
                    )
                )
            )
            for existing_pack in conflicting_existing_packs:
                existing_pack.pack_code = None
                existing_pack.updated_at = now

            product = session.scalar(
                select(CigaretteProduct).where(
                    CigaretteProduct.carton_code == row.carton_code
                )
            )
            if product is None:
                product = CigaretteProduct(carton_code=row.carton_code)
                session.add(product)
                created_count += 1
            else:
                updated_count += 1
            product.pack_code = pack_code
            product.brand = row.brand
            product.standard_name = row.standard_name
            product.carton_retail_price = row.carton_retail_price
            product.sticks_per_pack = row.sticks_per_pack
            product.packs_per_carton = row.packs_per_carton
            product.is_active = True
            product.updated_at = now
        session.commit()
    except Exception:
        session.rollback()
        raise

    issues.sort(key=lambda item: (item.row_number, item.level, item.code))
    error_rows = {issue.row_number for issue in issues if issue.level == "ERROR"}
    warning_count = sum(issue.level == "WARNING" for issue in issues)
    return ImportResult(
        total_rows=parsed.total_rows,
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=len(error_rows),
        warning_count=warning_count,
        issues=issues,
    )
