import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.finalization import ExportRecord, ScanItemSourceAllocation
from app.models.scanning import ScanEvent, ScanSessionItem
from app.scanning.service import china_datetime, get_scan_session, serialize_scan_session
from app.scanning.source_service import serialize_allocation
from app.schemas.auth import AuthUser

TEMPLATE_VERSION = "1.0"
TEXT_FORMAT = "@"
MONEY_FORMAT = "¥#,##0.00"
DATE_TIME_FORMAT = "yyyy/mm/dd hh:mm:ss"


class ExportSessionNotCompletedError(ValueError):
    pass


class ExportEmptyError(ValueError):
    pass


@dataclass(frozen=True)
class GeneratedExport:
    content: bytes
    filename: str
    record: ExportRecord


def china_excel_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return china_datetime(value).replace(tzinfo=None)


def export_filename(session_no: str, generated_at: datetime) -> str:
    china_time = china_datetime(generated_at)
    return f"涉案卷烟统计_{session_no}_{china_time:%Y%m%d_%H%M%S}.xlsx"


def style_header(sheet, row: int, columns: int) -> None:
    fill = PatternFill("solid", fgColor="1F6B5B")
    border = Border(bottom=Side(style="thin", color="D6E2DE"))
    for column in range(1, columns + 1):
        cell = sheet.cell(row, column)
        cell.fill = fill
        cell.font = Font(name="Microsoft YaHei", color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border


def style_body(sheet, *, header_rows: set[int] | None = None) -> None:
    header_rows = header_rows or {1}
    for row in sheet.iter_rows():
        for cell in row:
            if cell.row not in header_rows:
                cell.font = Font(name="Microsoft YaHei", size=10)
            cell.alignment = Alignment(vertical="center", wrap_text=True)


def set_widths(sheet, widths: list[float]) -> None:
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width


def append_registration_sheet(workbook: Workbook, data: dict[str, Any]) -> None:
    sheet = workbook.active
    sheet.title = "卷烟登记表"
    sheet.merge_cells("A1:L1")
    sheet["A1"] = "卷烟登记表"
    sheet["A1"].font = Font(name="Microsoft YaHei", size=18, bold=True, color="173F37")
    sheet["A1"].alignment = Alignment(horizontal="center")

    session = data["session"]
    summary = data["summary"]
    metadata = [
        ("标识", session["display_label"]),
        ("承办单位", session["branch_name"]),
        ("立案编号", session["filing_case_no"] or ""),
        (
            "累计扫描数量",
            f"{summary['equivalent_cartons']} 条 / {summary['total_sticks']} 支",
        ),
        ("累计零售价合计", summary["reference_amount"]),
    ]
    for row_index, (label, value) in enumerate(metadata, start=3):
        sheet.cell(row_index, 1, label).font = Font(name="Microsoft YaHei", bold=True)
        sheet.merge_cells(start_row=row_index, start_column=2, end_row=row_index, end_column=12)
        sheet.cell(row_index, 2, value)
    sheet.cell(7, 2).number_format = MONEY_FORMAT

    header_row = 9
    headers = [
        "序号",
        "品规名称",
        "条形码",
        "品牌",
        "类型",
        "条支比",
        "零售价（条）",
        "查获数量（条）",
        "查获数量（支）",
        "卷烟来源地类型",
        "来源省",
        "来源市",
    ]
    sheet.append([])
    sheet.append(headers)
    style_header(sheet, header_row, len(headers))
    sequence = 1
    for item in data["items"]:
        product = item["product_snapshot"]
        for allocation in item["allocations"]:
            sheet.append(
                [
                    sequence,
                    product["standard_name"],
                    str(product["carton_code"]),
                    product["brand"],
                    "卷烟",
                    product["sticks_per_carton"],
                    float(product["carton_retail_price"])
                    if product["carton_retail_price"] is not None
                    else None,
                    float(allocation["equivalent_cartons"]),
                    allocation["quantity_sticks"],
                    allocation["source_type_name"],
                    allocation["province_name"] or "",
                    allocation["city_name"] or "",
                ]
            )
            row = sheet.max_row
            sheet.cell(row, 3).number_format = TEXT_FORMAT
            sheet.cell(row, 7).number_format = MONEY_FORMAT
            sheet.cell(row, 8).number_format = "0.0"
            sequence += 1
    sheet.freeze_panes = f"A{header_row + 1}"
    sheet.auto_filter.ref = f"A{header_row}:L{sheet.max_row}"
    set_widths(sheet, [8, 28, 20, 14, 10, 10, 15, 16, 16, 18, 16, 18])
    style_body(sheet, header_rows={1, header_row})


def append_summary_sheet(workbook: Workbook, data: dict[str, Any]) -> None:
    sheet = workbook.create_sheet("品规汇总")
    headers = [
        "序号",
        "品牌",
        "品规名称",
        "条形码",
        "条支比",
        "每包支数",
        "零售价（条）",
        "最终包数",
        "折合条数",
        "总支数",
        "参考金额",
    ]
    sheet.append(headers)
    style_header(sheet, 1, len(headers))
    for sequence, item in enumerate(data["items"], start=1):
        product = item["product_snapshot"]
        sheet.append(
            [
                sequence,
                product["brand"],
                product["standard_name"],
                str(product["carton_code"]),
                product["sticks_per_carton"],
                product["sticks_per_pack"],
                float(product["carton_retail_price"])
                if product["carton_retail_price"] is not None
                else None,
                item["pack_count"],
                float(item["equivalent_cartons"]),
                item["total_sticks"],
                float(item["reference_amount"]),
            ]
        )
        row = sheet.max_row
        sheet.cell(row, 4).number_format = TEXT_FORMAT
        sheet.cell(row, 7).number_format = MONEY_FORMAT
        sheet.cell(row, 9).number_format = "0.0"
        sheet.cell(row, 11).number_format = MONEY_FORMAT
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:K{sheet.max_row}"
    set_widths(sheet, [8, 14, 28, 20, 10, 12, 15, 12, 12, 12, 15])
    style_body(sheet)


def append_events_sheet(workbook: Workbook, data: dict[str, Any]) -> None:
    sheet = workbook.create_sheet("操作流水")
    headers = [
        "时间",
        "事件类型",
        "结果",
        "原始编码",
        "品规名称",
        "单位",
        "变化支数",
        "操作人",
        "原因",
    ]
    sheet.append(headers)
    style_header(sheet, 1, len(headers))
    for event in data["events"]:
        product = event.get("product_snapshot") or {}
        sheet.append(
            [
                china_excel_datetime(event["created_at"]),
                event["event_type"],
                event["result"],
                str(event["raw_code"]),
                product.get("standard_name", ""),
                event.get("unit_type") or "",
                event["delta_sticks"],
                event["operator_name"],
                event.get("reason") or "",
            ]
        )
        row = sheet.max_row
        sheet.cell(row, 1).number_format = DATE_TIME_FORMAT
        sheet.cell(row, 4).number_format = TEXT_FORMAT
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:I{sheet.max_row}"
    set_widths(sheet, [20, 14, 14, 20, 28, 12, 12, 16, 40])
    style_body(sheet)


def append_exceptions_sheet(workbook: Workbook, data: dict[str, Any]) -> None:
    sheet = workbook.create_sheet("异常编码")
    headers = ["编码", "异常类型", "候选品规", "发生时间", "处理状态"]
    sheet.append(headers)
    style_header(sheet, 1, len(headers))
    for event in data["exceptions"]:
        sheet.append(
            [
                str(event["raw_code"]),
                event["exception_type"],
                event["candidate_names"],
                china_excel_datetime(event["created_at"]),
                event["status"],
            ]
        )
        row = sheet.max_row
        sheet.cell(row, 1).number_format = TEXT_FORMAT
        sheet.cell(row, 4).number_format = DATE_TIME_FORMAT
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:E{sheet.max_row}"
    set_widths(sheet, [22, 16, 42, 20, 16])
    style_body(sheet)


def build_export_workbook(data: dict[str, Any]) -> bytes:
    workbook = Workbook()
    workbook.properties.title = "涉案卷烟统计"
    workbook.properties.subject = f"模板版本 {TEMPLATE_VERSION}"
    append_registration_sheet(workbook, data)
    append_summary_sheet(workbook, data)
    append_events_sheet(workbook, data)
    append_exceptions_sheet(workbook, data)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def reference_amount(item: ScanSessionItem) -> Decimal:
    snapshot = item.product_snapshot
    price_text = snapshot.get("carton_retail_price")
    if price_text is None:
        return Decimal("0.00")
    return (
        Decimal(str(price_text))
        * Decimal(item.total_sticks)
        / Decimal(int(snapshot["sticks_per_carton"]))
    ).quantize(Decimal("0.01"))


def build_export_data(
    session: Session,
    current_user: AuthUser,
    session_id: int,
) -> dict[str, object]:
    batch = get_scan_session(session, current_user, session_id)
    if batch.status != "COMPLETED":
        raise ExportSessionNotCompletedError("只能导出已完成的扫描批次")
    items = list(
        session.scalars(
            select(ScanSessionItem)
            .where(
                ScanSessionItem.session_id == session_id,
                ScanSessionItem.total_sticks > 0,
            )
            .order_by(ScanSessionItem.id)
        )
    )
    if not items:
        raise ExportEmptyError("批次没有可导出的卷烟品规")

    serialized_items: list[dict[str, object]] = []
    total_pack_count = 0
    total_sticks = 0
    total_amount = Decimal("0.00")
    for item in items:
        snapshot = item.product_snapshot
        sticks_per_pack = int(snapshot["sticks_per_pack"])
        pack_count = item.total_sticks // sticks_per_pack
        amount = reference_amount(item)
        allocations = list(
            session.scalars(
                select(ScanItemSourceAllocation)
                .where(ScanItemSourceAllocation.session_item_id == item.id)
                .order_by(ScanItemSourceAllocation.id)
            )
        )
        serialized_items.append(
            {
                "product_snapshot": snapshot,
                "total_sticks": item.total_sticks,
                "pack_count": pack_count,
                "equivalent_cartons": Decimal(pack_count) / Decimal(10),
                "reference_amount": amount,
                "allocations": [serialize_allocation(row) for row in allocations],
            }
        )
        total_pack_count += pack_count
        total_sticks += item.total_sticks
        total_amount += amount

    event_rows = list(
        session.execute(
            select(ScanEvent, User.display_name)
            .join(User, User.id == ScanEvent.operator_id)
            .where(ScanEvent.session_id == session_id)
            .order_by(ScanEvent.created_at, ScanEvent.id)
        )
    )
    events = [
        {
            "id": event.id,
            "created_at": event.created_at,
            "event_type": event.event_type,
            "result": event.result,
            "raw_code": event.raw_code,
            "product_snapshot": event.product_snapshot,
            "candidate_snapshot": event.candidate_snapshot,
            "unit_type": event.unit_type,
            "delta_sticks": event.delta_sticks,
            "operator_name": operator_name,
            "reason": event.reason,
        }
        for event, operator_name in event_rows
    ]
    resolved_ids = {
        event.source_event_id
        for event, _ in event_rows
        if event.source_event_id is not None
    }
    exceptions = []
    for event, _ in event_rows:
        if event.result == "UNKNOWN":
            exception_type = "未识别"
        elif event.result == "AMBIGUOUS" and event.id not in resolved_ids:
            exception_type = "未解决歧义"
        else:
            continue
        candidates = event.candidate_snapshot or []
        exceptions.append(
            {
                "raw_code": event.raw_code,
                "exception_type": exception_type,
                "candidate_names": "、".join(
                    str(candidate.get("standard_name", "")) for candidate in candidates
                ),
                "created_at": event.created_at,
                "status": "未处理",
            }
        )

    serialized_session = serialize_scan_session(session, batch)
    return {
        "session": serialized_session,
        "summary": {
            "product_count": len(items),
            "total_pack_count": total_pack_count,
            "total_sticks": total_sticks,
            "equivalent_cartons": Decimal(total_pack_count) / Decimal(10),
            "reference_amount": total_amount.quantize(Decimal("0.01")),
        },
        "items": serialized_items,
        "events": events,
        "exceptions": exceptions,
    }


def generate_session_export(
    session: Session,
    current_user: AuthUser,
    session_id: int,
    *,
    now: datetime,
) -> GeneratedExport:
    data = build_export_data(session, current_user, session_id)
    content = build_export_workbook(data)
    session_data = data["session"]
    if not isinstance(session_data, dict):
        raise TypeError("导出批次数据格式错误")
    filename = export_filename(str(session_data["session_no"]), now)
    record = ExportRecord(
        session_id=session_id,
        filename=filename,
        file_size=len(content),
        file_sha256=hashlib.sha256(content).hexdigest(),
        template_version=TEMPLATE_VERSION,
        generated_by=current_user.id,
        created_at=now,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return GeneratedExport(content=content, filename=filename, record=record)
