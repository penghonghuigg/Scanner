from datetime import datetime
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from app.scanning.export_service import build_export_workbook, export_filename


def export_fixture() -> dict[str, object]:
    product = {
        "product_id": 42,
        "carton_code": "6901028129756",
        "pack_code": "6901028129757",
        "brand": "黄山",
        "standard_name": "黄山(红方印金中支)",
        "carton_retail_price": "400.00",
        "sticks_per_pack": 20,
        "packs_per_carton": 10,
        "sticks_per_carton": 200,
    }
    return {
        "session": {
            "session_no": "PD20260902-150000-0001",
            "display_label": "2026-09-02 15:00—彭鸿徽—1个品规—360支卷烟",
            "branch_name": "凤台县局",
            "filing_case_no": "3404210202610010",
            "business_type_name": "市场检查",
            "location": "测试地点",
            "notes": None,
            "operator_name": "彭鸿徽",
            "created_at": datetime(2026, 9, 2, 7, 0, 0),
            "completed_at": datetime(2026, 9, 2, 8, 0, 0),
        },
        "summary": {
            "product_count": 1,
            "total_pack_count": 18,
            "total_sticks": 360,
            "equivalent_cartons": Decimal("1.8"),
            "reference_amount": Decimal("720.00"),
        },
        "items": [
            {
                "product_snapshot": product,
                "total_sticks": 360,
                "pack_count": 18,
                "equivalent_cartons": Decimal("1.8"),
                "reference_amount": Decimal("720.00"),
                "allocations": [
                    {
                        "source_type_name": "外省流入",
                        "province_name": "天津市",
                        "city_name": "不详",
                        "pack_count": 15,
                        "equivalent_cartons": Decimal("1.5"),
                        "quantity_sticks": 300,
                    },
                    {
                        "source_type_name": "来源不详",
                        "province_name": None,
                        "city_name": None,
                        "pack_count": 3,
                        "equivalent_cartons": Decimal("0.3"),
                        "quantity_sticks": 60,
                    },
                ],
            }
        ],
        "events": [
            {
                "created_at": datetime(2026, 9, 2, 7, 10, 0),
                "event_type": "SCAN",
                "result": "SUCCESS",
                "raw_code": "6901028129756",
                "product_snapshot": product,
                "unit_type": "CARTON",
                "delta_sticks": 200,
                "operator_name": "彭鸿徽",
                "reason": None,
            },
            {
                "created_at": datetime(2026, 9, 2, 7, 20, 0),
                "event_type": "SCAN",
                "result": "UNKNOWN",
                "raw_code": "6999999999999",
                "product_snapshot": None,
                "candidate_snapshot": None,
                "unit_type": None,
                "delta_sticks": 0,
                "operator_name": "彭鸿徽",
                "reason": None,
            },
        ],
        "exceptions": [
            {
                "raw_code": "6999999999999",
                "exception_type": "未识别",
                "candidate_names": "",
                "created_at": datetime(2026, 9, 2, 7, 20, 0),
                "status": "未处理",
            }
        ],
    }


def workbook():
    return load_workbook(BytesIO(build_export_workbook(export_fixture())))


def find_header_row(sheet, header: str) -> int:
    for row in range(1, sheet.max_row + 1):
        if sheet.cell(row, 1).value == header:
            return row
    raise AssertionError(f"没有找到表头 {header}")


def test_export_workbook_has_exact_four_sheet_names() -> None:
    assert workbook().sheetnames == ["卷烟登记表", "品规汇总", "操作流水", "异常编码"]


def test_registration_sheet_repeats_product_fields_and_includes_sticks() -> None:
    sheet = workbook()["卷烟登记表"]
    header_row = find_header_row(sheet, "序号")
    headers = [sheet.cell(header_row, column).value for column in range(1, 13)]
    assert headers == [
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
    first = header_row + 1
    second = header_row + 2
    assert sheet.cell(first, 2).value == "黄山(红方印金中支)"
    assert sheet.cell(second, 2).value == "黄山(红方印金中支)"
    assert sheet.cell(first, 8).value == 1.5
    assert sheet.cell(first, 9).value == 300
    assert sheet.cell(second, 8).value == 0.3
    assert sheet.cell(second, 9).value == 60
    assert sheet.cell(first, 10).value == "外省流入"
    assert sheet.cell(second, 10).value == "来源不详"
    assert sheet.cell(first, 11).value == "天津市"
    assert sheet.cell(first, 12).value == "不详"


def test_codes_are_text_and_amounts_and_times_have_business_formats() -> None:
    result = workbook()
    registration = result["卷烟登记表"]
    header_row = find_header_row(registration, "序号")
    code_cell = registration.cell(header_row + 1, 3)
    assert code_cell.value == "6901028129756"
    assert code_cell.data_type == "s"
    assert code_cell.number_format == "@"
    assert registration.cell(header_row + 1, 7).number_format == "¥#,##0.00"
    assert registration.cell(header_row + 1, 8).number_format == "0.0"

    events = result["操作流水"]
    assert events.cell(2, 1).number_format == "yyyy/mm/dd hh:mm:ss"
    assert events.cell(2, 4).data_type == "s"
    assert events.cell(2, 4).number_format == "@"
    exceptions = result["异常编码"]
    assert exceptions.cell(2, 1).data_type == "s"
    assert exceptions.cell(2, 1).number_format == "@"


def test_export_filename_contains_session_number_and_china_timestamp() -> None:
    assert export_filename(
        "PD20260902-150000-0001",
        datetime(2026, 9, 2, 8, 30, 45),
    ) == "涉案卷烟统计_PD20260902-150000-0001_20260902_163045.xlsx"
