from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.integrations.jiandaoyun import (  # noqa: E402
    ExternalRejectedError,
    ExternalUncertainError,
    JianDaoYunConfig,
    build_registration_data,
    create_registration,
)


def demo_export_data(now: datetime | None = None) -> dict[str, object]:
    timestamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M")
    return {
        "session": {
            "display_label": f"{timestamp}—接口测试—1个品规—20支卷烟",
            "branch_name": "测试单位",
            "filing_case_no": "",
            "operator_name": "接口测试",
        },
        "items": [
            {
                "product_snapshot": {
                    "carton_code": "6900000000000",
                    "standard_name": "接口连通性测试卷烟",
                    "brand": "测试品牌",
                    "sticks_per_carton": 200,
                },
                "total_sticks": 20,
                "equivalent_cartons": Decimal("0.1"),
            }
        ],
    }


def main(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="简道云新建单条数据接口联调工具")
    parser.add_argument("--send", action="store_true", help="创建一条可删除的测试数据")
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    data = build_registration_data(demo_export_data())

    if not args.send:
        print("DRY-RUN：未访问外部接口。使用 --send 才会创建测试数据。")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    try:
        config = JianDaoYunConfig(
            create_url=env.get("JIANDAOYUN_CREATE_URL", ""),
            app_id=env.get("JIANDAOYUN_APP_ID", ""),
            entry_id=env.get("JIANDAOYUN_ENTRY_ID", ""),
            api_key=env.get("JIANDAOYUN_API_KEY", ""),
        )
    except ValueError as exc:
        print(f"错误：{exc}，请设置四项 JIANDAOYUN_* 环境变量。", file=sys.stderr)
        return 2

    print("即将创建 1 条可删除的接口连通性测试数据，不会自动重试。")
    try:
        result = create_registration(config, data)
    except (ExternalRejectedError, ExternalUncertainError) as exc:
        print(f"联调失败：{exc}", file=sys.stderr)
        return 1

    print("联调成功。")
    print(f"外部数据 ID：{result.data_id}")
    if result.created_at:
        print(f"创建时间：{result.created_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
