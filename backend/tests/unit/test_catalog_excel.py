from importlib import import_module
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

HEADERS = ["条码", "品规名称", "包码", "品牌", "零售价格", "包数量", "条数量"]


def catalog_excel():
    try:
        return import_module("app.catalog.excel")
    except ModuleNotFoundError:
        pytest.fail("app.catalog.excel 尚未实现")


def workbook_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(HEADERS)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_template_has_data_and_instruction_sheets_with_text_code_columns() -> None:
    excel = catalog_excel()

    workbook = load_workbook(BytesIO(excel.build_import_template()))

    assert workbook.sheetnames == ["品规导入", "填写说明"]
    data_sheet = workbook["品规导入"]
    assert [cell.value for cell in data_sheet[1]] == HEADERS
    assert data_sheet["A2"].number_format == "@"
    assert data_sheet["C2"].number_format == "@"
    assert workbook["填写说明"]["A1"].value == "字段"


def test_parser_cleans_unknown_values_and_derives_package_conversion() -> None:
    excel = catalog_excel()
    content = workbook_bytes(
        [
            ["6901028000011", "测试烟（经典）", "6901028000028", "测试烟", 100, 20, 200],
            ["6901028000035", "测试烟（单盒）", -1, "测试烟", -1, -1, 50],
        ]
    )

    result = excel.parse_import_workbook(content)

    assert result.total_rows == 2
    assert result.issues == []
    assert result.rows[0].sticks_per_pack == 20
    assert result.rows[0].packs_per_carton == 10
    assert str(result.rows[0].carton_retail_price) == "100.00"
    assert result.rows[1].pack_code is None
    assert result.rows[1].carton_retail_price is None
    assert result.rows[1].sticks_per_pack == 50
    assert result.rows[1].packs_per_carton == 1


def test_parser_rejects_duplicate_codes_and_invalid_package_rows() -> None:
    excel = catalog_excel()
    content = workbook_bytes(
        [
            ["6901028000059", "重复一", -1, "测试烟", 100, 20, 200],
            ["6901028000059", "重复二", -1, "测试烟", 100, 20, 200],
            ["6901028000066", "缺少包数量", "6901028000073", "测试烟", 100, -1, 200],
            ["6901028000080", "不能整除", "6901028000097", "测试烟", 100, 16, 200],
        ]
    )

    result = excel.parse_import_workbook(content)

    assert result.total_rows == 4
    assert result.rows == []
    assert [(issue.row_number, issue.code) for issue in result.issues] == [
        (2, "CARTON_CODE_DUPLICATE"),
        (3, "CARTON_CODE_DUPLICATE"),
        (4, "PACKAGE_QUANTITY_INVALID"),
        (5, "PACKAGE_CONVERSION_INVALID"),
    ]
