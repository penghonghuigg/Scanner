# 简道云新建单条数据接口联调 Demo 设计

## 1. 目标

先用一个独立 Python Demo 验证当前服务器能否访问简道云私有化接口，并确认主表、子表字段格式正确。Demo 不接入前端，不读取或修改本系统数据库，也不改变现有盘点流程。

验证成功后，再单独设计“已完成批次一键导入简道云”功能。

## 2. 接口配置

- 请求方式：`POST`
- 请求地址：只从环境变量 `JIANDAOYUN_CREATE_URL` 读取，仓库不提供真实默认值
- 应用 ID：只从环境变量 `JIANDAOYUN_APP_ID` 读取，仓库不提供真实默认值
- 表单 ID：只从环境变量 `JIANDAOYUN_ENTRY_ID` 读取，仓库不提供真实默认值
- API Key：从环境变量 `JIANDAOYUN_API_KEY` 读取
- 鉴权请求头：`Authorization: Bearer <API Key>`
- 内容类型：`application/json; charset=utf-8`
- 请求超时：连接 5 秒，读取 20 秒

真实 API Key 不写入脚本、`.env.example`、日志、测试快照或 Git。`.env.example` 只保存空白配置项和公开的接口结构示例。

## 3. 运行方式

脚本路径：`backend/scripts/test_jiandaoyun_create.py`。

- 默认模式：构造并打印脱敏请求，不访问外部接口。
- `--send`：向真实接口创建一条测试数据。
- 没有 `--send` 时，即使配置了 API Key 也不产生外部写入。
- 真实发送前，在控制台明确显示目标主机、应用 ID、表单 ID 和测试标识，但不显示 API Key。

当前项目使用 Conda 结构的虚拟环境，已验证的 Windows PowerShell 命令为：

```powershell
backend\.venv\python.exe backend\scripts\test_jiandaoyun_create.py
backend\.venv\python.exe backend\scripts\test_jiandaoyun_create.py --send
```

测试记录的标识以 `接口连通性测试-可删除-<时间>` 开头，便于在简道云中定位和删除。

## 4. 字段映射

### 4.1 主表

| 简道云字段 | 字段 ID | Demo 值 |
|---|---|---|
| 标识 ID | `_widget_1788244617469` | `接口连通性测试-可删除-<时间>` |
| 县（分）局 | `_widget_1788244617474` | `凤台县局` |
| 立案编号 | `_widget_1788244617473` | `API-DEMO-<时间>` |
| 登记人员 | `_widget_1788244617475` | `接口测试` |
| 登记卷烟列表 | `_widget_1788244617471` | 1 条子表测试数据 |

### 4.2 子表

| 简道云字段 | 字段 ID | 类型 | Demo 值 |
|---|---|---|---|
| 条包装条形码 | `_widget_1788247452462` | text | `6900000000000` |
| 品规名称 | `_widget_1788245720805` | text | `接口连通性测试卷烟` |
| 品牌 | `_widget_1788247452464` | text | `测试品牌` |
| 类型 | `_widget_1788247452463` | text | `卷烟` |
| 条支比 | `_widget_1788247452467` | number | `200` |
| 入库数量（条） | `_widget_1788247452468` | number | `0.1` |

请求中的字段保持简道云要求的 `{ "value": ... }` 包装；子表字段放在子表 `value` 数组的行对象中。

## 5. 请求示例

```json
{
  "app_id": "<JIANDAOYUN_APP_ID>",
  "entry_id": "<JIANDAOYUN_ENTRY_ID>",
  "is_start_workflow": false,
  "is_start_trigger": false,
  "data": {
    "_widget_1788244617469": {
      "value": "接口连通性测试-可删除-20260904-120000"
    },
    "_widget_1788244617474": {
      "value": "凤台县局"
    },
    "_widget_1788244617473": {
      "value": "API-DEMO-20260904-120000"
    },
    "_widget_1788244617475": {
      "value": "接口测试"
    },
    "_widget_1788244617471": {
      "value": [
        {
          "_widget_1788247452462": { "value": "6900000000000" },
          "_widget_1788245720805": { "value": "接口连通性测试卷烟" },
          "_widget_1788247452464": { "value": "测试品牌" },
          "_widget_1788247452463": { "value": "卷烟" },
          "_widget_1788247452467": { "value": 200 },
          "_widget_1788247452468": { "value": 0.1 }
        }
      ]
    }
  }
}
```

## 6. 响应和退出码

- HTTP 2xx 且响应含 `data._id`：联调成功，控制台输出外部数据 ID、创建时间和测试标识。
- HTTP 非 2xx：输出状态码及经过长度限制的响应内容，退出码为非 0。
- HTTP 2xx 但缺少 `data._id`：按协议异常处理，退出码为非 0。
- 网络错误、TLS 错误或超时：只输出错误类型和目标主机，不输出请求头或 API Key。
- 不自动重试真实创建请求，避免网络边界不明确时生成重复数据。

## 7. 测试设计

先为纯函数编写单元测试，再实现 Demo：

1. 请求体包含全部主表和子表字段，数字保持 JSON number；
2. `Authorization` 自动增加 `Bearer ` 前缀，已有前缀时不重复增加；
3. 默认模式不发起 HTTP 请求；
4. `--send` 缺少任一配置时拒绝执行；
5. 输出内容不包含 API Key；
6. 成功响应必须提取 `data._id`；
7. HTTP 错误、非 JSON 响应和超时返回非 0 退出码；
8. 使用 Mock HTTP 客户端完成自动化测试，自动测试不得访问真实简道云。

真实联调只人工执行 1 次，并将外部数据 ID 报告给用户；脚本不会自动删除简道云测试数据。

## 8. 范围外

- 不增加前端“一键导入简道云”按钮；
- 不增加数据库表或修改现有数据；
- 不从已完成批次读取真实卷烟；
- 不实现自动重试、定时任务或批量推送；
- 不启动简道云工作流和智能助手；
- 不把 API Key 写入任何仓库文件。

以上内容将在 Demo 联调成功后，作为正式阶段 8 设计的输入。
