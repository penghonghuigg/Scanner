# 涉案卷烟智能统计系统软件需求规格说明书（SPEC）

## 1. 文档信息

| 项目 | 内容 |
|---|---|
| 文档版本 | V1.0 |
| 目标读者 | 后端、前端、测试、运维及接口研发人员 |
| 系统形态 | 前后端分离的内网 Web 应用 |
| 数据库 | MySQL 8.x |
| 部署方式 | Docker Compose |

## 2. 系统边界

系统负责卷烟基础数据管理、扫描批次、编码识别、数量统计、Excel 导出、审计以及简道云罚没烟登记快照和一键导入。系统不负责完整仓储管理、执法文书、审批流及简道云内部后续业务。

## 3. 系统组件

| 组件 | 职责 |
|---|---|
| `web` | Vue 3 前端，接收扫码枪输入并展示结果 |
| `nginx` | 静态资源、TLS、反向代理和基础限流 |
| `api` | FastAPI 业务服务和 OpenAPI 文档 |
| `mysql` | 业务数据、审计数据和接口快照 |
| `backup` | 定时执行数据库备份和保留策略 |

后端按领域拆分为 `auth`、`catalog`、`scanning`、`exports`、`integrations`、`audit` 六个模块。模块之间通过服务接口交互，不允许控制器直接跨模块修改数据表。

## 4. 技术约束

- Python 3.12；
- FastAPI、Pydantic、SQLAlchemy 2.x；
- SQLAlchemy metadata 定义数据库结构，显式 `init_db` 命令只创建缺失表；
- MySQL 使用 InnoDB 和 `utf8mb4`；
- Vue 3、TypeScript、Vite；
- API 前缀统一为 `/api/v1`；
- 时间在数据库中保存 UTC，API 使用 ISO 8601；
- 金额使用 `DECIMAL`，条码和业务编号使用字符类型；
- JSON 属性和接口快照使用 MySQL `JSON` 类型。

## 5. 数据模型

### 5.1 `users`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键、自增 |
| `username` | VARCHAR(64) | 唯一、非空 |
| `password_hash` | VARCHAR(255) | 非空 |
| `display_name` | VARCHAR(100) | 非空 |
| `role` | VARCHAR(20) | ADMIN、OPERATOR、VIEWER |
| `branch_code` | VARCHAR(20) | 五个县分局代码；管理员可空 |
| `is_active` | BOOLEAN | 默认 true |
| `created_at` | DATETIME(6) | UTC |
| `updated_at` | DATETIME(6) | UTC |

### 5.2 `user_sessions`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `user_id` | BIGINT UNSIGNED | 登录用户，外键 |
| `token_hash` | VARCHAR(64) | 服务端会话摘要，唯一 |
| `expires_at` | DATETIME(6) | 过期时间，UTC |
| `revoked_at` | DATETIME(6) | 注销时间，可空 |
| `created_at` | DATETIME(6) | UTC |

### 5.3 `cigarette_products`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `carton_code` | VARCHAR(64) | 条码，唯一 |
| `pack_code` | VARCHAR(64) | 包码，可空；允许跨记录重复形成歧义 |
| `brand` | VARCHAR(100) | 品牌 |
| `standard_name` | VARCHAR(200) | 标准品规名称 |
| `carton_retail_price` | DECIMAL(12,2) | 每条参考零售价，可空 |
| `sticks_per_pack` | SMALLINT UNSIGNED | 每包支数 |
| `packs_per_carton` | SMALLINT UNSIGNED | 每条包数；每条支数由两者相乘计算 |
| `is_active` | BOOLEAN | 是否启用 |
| `created_at` | DATETIME(6) | UTC |
| `updated_at` | DATETIME(6) | UTC |

索引：`UNIQUE(carton_code)`、`INDEX(pack_code, is_active)`、`INDEX(brand, standard_name)`。Excel 导入结果随请求返回，不新增导入批次或错误明细表。

### 5.6 `scan_sessions`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `session_no` | VARCHAR(40) | 唯一业务编号 |
| `business_type` | VARCHAR(32) | MARKET_INSPECTION、DELIVERY_CHANNEL、SPECIAL_TRANSPORT、OTHER |
| `filing_case_no` | VARCHAR(100) | 立案编号，可空 |
| `location` | VARCHAR(200) | 扫描地点，可空 |
| `notes` | VARCHAR(500) | 备注，可空 |
| `branch_code` | VARCHAR(20) | 所属县分局 |
| `operator_id` | BIGINT UNSIGNED | 创建操作员 |
| `status` | VARCHAR(16) | DRAFT、COMPLETED |
| `completed_at` | DATETIME(6) | 完成时间，可空 |
| `created_at` | DATETIME(6) | UTC |
| `updated_at` | DATETIME(6) | UTC |

索引：`UNIQUE(session_no)`、`INDEX(branch_code, status, created_at)`、`INDEX(operator_id, created_at)`。

### 5.7 `scan_events`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `request_id` | CHAR(36) | 客户端幂等请求号，唯一 |
| `session_id` | BIGINT UNSIGNED | 扫描批次 |
| `event_type` | VARCHAR(24) | SCAN、ADJUST、RESOLVE、VOID |
| `result` | VARCHAR(24) | SUCCESS、UNKNOWN、AMBIGUOUS |
| `raw_code` | VARCHAR(64) | 原始编码 |
| `product_id` | BIGINT UNSIGNED | 匹配品规，可空 |
| `unit_type` | VARCHAR(16) | CARTON、PACK、STICK，可空 |
| `delta_sticks` | INT | 本次总支数变化 |
| `source_event_id` | BIGINT UNSIGNED | 歧义解决所对应的原事件，可空且唯一 |
| `reason` | VARCHAR(500) | 调整或异常说明 |
| `candidate_snapshot` | JSON | 歧义候选快照，可空 |
| `product_snapshot` | JSON | 扫码时品规快照，可空 |
| `operator_id` | BIGINT UNSIGNED | 操作人 |
| `created_at` | DATETIME(6) | UTC |

`scan_events` 只允许追加，不提供物理删除接口。

### 5.8 `scan_session_items`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `session_id` | BIGINT UNSIGNED | 批次 |
| `product_id` | BIGINT UNSIGNED | 品规 |
| `carton_count` | INT UNSIGNED | 条码成功扫描次数 |
| `pack_count` | INT UNSIGNED | 包码成功扫描次数 |
| `manual_delta_sticks` | INT | 人工调整支数 |
| `total_sticks` | INT UNSIGNED | 当前总支数 |
| `product_snapshot` | JSON | 品规名称、品牌、价格、条支比快照 |
| `updated_at` | DATETIME(6) | UTC |

约束：`UNIQUE(session_id, product_id)`。`total_sticks` 必须大于等于 0。

### 5.9 来源拆分表 `scan_item_source_allocations`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `session_item_id` | BIGINT UNSIGNED | 批次品规汇总项，外键，删除汇总项时级联删除 |
| `source_type` | VARCHAR(32) | `OUTSIDE_PROVINCE`、`UNKNOWN`、`LOCAL_HUAINAN`、`ANHUI_OTHER_CITY` |
| `province_name` | VARCHAR(50) | 来源省，可空 |
| `city_name` | VARCHAR(80) | 来源市，可空 |
| `pack_count` | INT UNSIGNED | 来源包数，必须大于 0 |
| `quantity_sticks` | INT UNSIGNED | 来源支数，等于包数 × 每包支数 |
| `source_key` | VARCHAR(200) | 标准化来源键，与 `session_item_id` 联合唯一 |
| `created_by` / `updated_by` | BIGINT UNSIGNED | 创建人和最后修改人 |
| `created_at` / `updated_at` | DATETIME(6) | UTC |

### 5.10 导出记录表 `export_records`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `session_id` | BIGINT UNSIGNED | 已完成批次，外键 |
| `filename` | VARCHAR(180) | 下载文件名 |
| `file_size` | BIGINT UNSIGNED | 内存文件字节数 |
| `file_sha256` | CHAR(64) | 文件 SHA-256 |
| `template_version` | VARCHAR(20) | 导出模板版本 |
| `generated_by` | BIGINT UNSIGNED | 导出操作人 |
| `created_at` | DATETIME(6) | UTC |

本表不包含服务器存储路径；`.xlsx` 只在内存中生成并直接返回浏览器。

### 5.11 简道云登记快照表 `integration_snapshots`

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `session_id` | BIGINT UNSIGNED | 唯一外键，关联 `scan_sessions.id` |
| `payload_json` | JSON | 首次导入时生成的不可变业务 `data`，不含接口配置和鉴权信息 |
| `payload_sha256` | CHAR(64) | 规范化 JSON 的 SHA-256 |
| `status` | VARCHAR(16) | PENDING、SUCCEEDED、FAILED、UNCERTAIN |
| `external_data_id` | VARCHAR(100) | 简道云数据 ID，可空 |
| `attempt_count` | INT UNSIGNED | 实际外部调用次数 |
| `last_error_code` | VARCHAR(64) | 脱敏错误分类，可空 |
| `last_error_message` | VARCHAR(500) | 脱敏错误摘要，可空 |
| `created_by` | BIGINT UNSIGNED | 首次生成快照的用户 |
| `last_attempted_by` | BIGINT UNSIGNED | 最近导入用户 |
| `created_at` | DATETIME(6) | UTC 创建时间 |
| `updated_at` | DATETIME(6) | UTC 更新时间 |
| `succeeded_at` | DATETIME(6) | UTC 成功时间，可空 |

`session_id` 唯一约束和事务行锁共同阻止并发重复导入。应用启动不自动执行 DDL，建表通过用户批准的独立 SQL 完成。

## 6. 编码识别规格

### 6.1 前端采集

1. 扫码输入框默认聚焦。
2. 接收 6～64 位数字编码，仅在按回车或点击“确认识别”时提交；输入达到任何长度都不自动提交。
3. 人工粘贴和手工输入使用相同校验逻辑。
4. 每次提交生成 UUID `request_id`。
5. 请求未完成时禁止使用相同输入重复提交。
6. 请求完成后清空输入并恢复焦点。

### 6.2 后端识别

```text
先按 `carton_code` 查询启用的 `cigarette_products`，无结果再按 `pack_code` 查询
├─ 条码匹配 1 条：SUCCESS，按一条更新汇总并记录事件
├─ 包码匹配 1 条：SUCCESS，按一包更新汇总并记录事件
├─ 包码匹配多条：AMBIGUOUS，返回候选项，不更新汇总
└─ 无匹配：UNKNOWN，记录事件，不更新汇总
```

### 6.3 扫码事务

扫码接口在一个数据库事务中完成：

1. 根据 `request_id` 查询既有结果；存在则直接返回原结果；
2. 使用 `SELECT ... FOR UPDATE` 锁定扫描批次；
3. 校验批次为 `DRAFT` 且用户有权限；
4. 查询编码并确定识别状态；
5. 对成功识别的汇总行执行锁定或创建；
6. 更新汇总值；
7. 插入 `scan_events`；
8. 提交事务并返回最新统计。

唯一的 `request_id` 约束作为最终幂等防线。

### 6.4 固定 0.1 条数量调整事务

阶段 5B 的 0.1 条调整复用现有两张扫码表，不新增 DDL。后端使用 `Decimal` 处理请求数量，并在一个事务中按以下顺序执行：

1. 使用 `SELECT ... FOR UPDATE` 锁定可写的 `DRAFT` 批次；
2. 以 `request_id`、批次、品规、操作、数量和调整原因校验幂等内容；
3. 锁定该批次的 `scan_session_items` 汇总行；
4. `quantity` 必须是 0.1 的整数倍；`DELTA` 在当前最终条数上增减，`SET` 设置非负且最多一位小数的最终条数；
5. 只更新 `manual_delta_sticks` 和 `total_sticks`，不覆盖 `carton_count`、`pack_count`；
6. 禁止最终条数或总支数小于 0；
7. 将 0.1 条换算为一包支数并写入整数支数；追加 `ADJUST/SUCCESS/CARTON` 事件，在 `reason` 中保存操作员选择的原因；
8. 提交后返回事件和最新权威扫码状态。

同一有效请求重放返回原事件且不重复调整；相同请求号对应不同内容时返回 `409 IDEMPOTENCY_CONFLICT`。

### 6.5 单个品规统计删除事务

删除复用 `scan_events` 与 `scan_session_items`，不新增 DDL。后端在同一事务中锁定有写权限的 `DRAFT` 批次，优先按 `request_id` 校验幂等内容，再锁定目标汇总行。首次删除追加 `ADJUST/SUCCESS/STICK` 事件，`delta_sticks` 等于删除前 `total_sticks` 的相反数，`reason` 固定为“删除品规统计：数量归零并隐藏”，并保留 `product_snapshot`；随后删除对应 `scan_session_items` 行。原有和新增 `scan_events` 均不删除。

相同有效请求重放时，即使汇总行已经不存在，也返回原事件与当前状态；请求号冲突返回 `409 IDEMPOTENCY_CONFLICT`；使用新请求号删除不存在的行返回 `404 SCAN_SESSION_ITEM_NOT_FOUND`。以后重新扫描相同条码时重新创建汇总行。

## 7. API 规格

### 7.1 通用响应

成功：

```json
{
  "success": true,
  "data": {},
  "trace_id": "01H..."
}
```

失败：

```json
{
  "success": false,
  "error": {
    "code": "SCAN_SESSION_CLOSED",
    "message": "当前批次已完成，不能继续扫码"
  },
  "trace_id": "01H..."
}
```

### 7.2 创建扫描批次

`POST /api/v1/scan-sessions`

```json
{
  "business_type": "MARKET_INSPECTION",
  "filing_case_no": "立案编号",
  "location": "涉案物品仓库",
  "notes": "首次登记",
  "branch_code": "FENGTAI"
}
```

管理员必须填写 `branch_code`；县分局操作员由后端固定为本人分局。返回完整批次字段及后端生成的“日期—姓名—品规数量—总卷烟支数”标识。

### 7.3 扫码

`POST /api/v1/scan-sessions/{session_id}/scan`

请求中的编码必须匹配 `^[0-9]{6,64}$`；不符合时返回 `422 BARCODE_INVALID`。

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "code": "6901028088060"
}
```

成功响应的 `data` 为 `ScanOperationResponse`：`event`、`state` 和 `idempotent_replay`。`state` 包含 `summary`、`items`、兼容字段 `recent_events`、`pending_ambiguities`、`catalog_summary` 和 `latest_successful_event`。其中 `catalog_summary` 精确包含 `active_code_count`、`active_standard_product_count`；事件包含可空的 `reason`。歧义返回 HTTP 200，事件 `result` 为 `AMBIGUOUS` 并携带候选快照，请求不更新汇总。

### 7.4 解决歧义

`POST /api/v1/scan-sessions/{session_id}/resolve`

```json
{
  "request_id": "新的 UUID",
  "event_id": 123,
  "product_id": 456
}
```

后端校验选中品规必须存在于原候选快照中。重复解决同一事件返回原结果，不重复计数。

### 7.5 固定 0.1 条人工调整

`POST /api/v1/scan-sessions/{session_id}/items/{product_id}/carton-quantity`

```json
{
  "request_id": "新的 UUID",
  "operation": "DELTA",
  "quantity": 0.1,
  "reason_type": "ONSITE_VERIFICATION",
  "reason_note": ""
}
```

`operation` 只能为 `DELTA` 或 `SET`。`quantity` 使用十进制定点数且必须是 0.1 的整数倍；`DELTA` 不得为 0，`SET` 不得小于 0。`reason_type` 必须为 `ONSITE_VERIFICATION`、`SCAN_CORRECTION`、`LOOSE_PACK_VERIFICATION`、`OTHER` 之一；选择 `OTHER` 时 `reason_note` 必填。后端组合数量变化和原因文字，追加 `ADJUST` 事件并返回 `ScanOperationResponse`。

### 7.6 扫码状态与流水分页

- `GET /api/v1/scan-sessions/{session_id}/scan-state` 返回 `ScanStateResponse`；
- `GET /api/v1/scan-sessions/{session_id}/events?page=1&page_size=10` 返回 `ScanEventListPayload`；
- `ScanEventListPayload` 精确包含 `items`、`total`、`page`、`page_size`；
- 流水按 `created_at DESC, id DESC` 排序，页面默认每页 10 条；
- `latest_successful_event` 仅取最近一次成功的 `SCAN` 或 `RESOLVE`，未知、歧义和人工调整不覆盖它。

#### 7.6.1 品规数量表展示

前端直接按 `ScanStateResponse.items` 顺序渲染单层标准 HTML 表格，一项一行，不按 `standard_name` 创建版本分组。同名称不同 `product_id` 或条码显示为平级行。10 列依次展示序号、品牌、标准品规、完整条码、固定类型“卷烟”、条支比、条零售价、数量调整控件、金额小计和删除操作。完整条码保持连续显示，最后 6 位使用红色粗体；长度不超过 6 位时整段高亮。表头与内容共享列宽并水平、垂直居中；保持表头约 13px、普通内容约 14px、品规名约 15px 加粗及条码约 13px 等宽字体。表格宽度为页面内容区的 100%，不设置强制最小宽度或横向滚动条，标准品规名称最多显示两行。调整仍使用该行 `product_id` 调用 7.5 接口。本阶段不渲染导出、CSV 或清空按钮。

#### 7.6.2 删除单个品规统计

`POST /api/v1/scan-sessions/{session_id}/items/{product_id}/remove`

```json
{
  "request_id": "新的 UUID"
}
```

请求模型只允许 `request_id`。成功响应沿用 `ScanOperationResponse`，精确包含删除事件、删除后的权威 `state` 和 `idempotent_replay`。前端确认框显示标准品规名称和条码；取消不发送请求，失败重试复用同一请求号。

### 7.7 来源地目录与来源拆分

- `GET /api/v1/regions`：返回四种来源类型以及去重后的省市目录；不返回香港、澳门；直辖市省市同名；台湾为台湾省、台湾省。
- `GET /api/v1/scan-sessions/{session_id}/source-allocations`：返回各有效品规的应分配、已分配、剩余包数和来源行。
- `PUT /api/v1/scan-sessions/{session_id}/items/{product_id}/source-allocations`：用请求中的完整来源行替换该品规来源。

来源约束：`OUTSIDE_PROVINCE` 必须选择非安徽省，`city_name` 为空或空字符串时由后端规范为“不详”，也可填写该省有效城市；`UNKNOWN` 不得携带省市；`LOCAL_HUAINAN` 固定为安徽省淮南市；`ANHUI_OTHER_CITY` 固定安徽省并选择淮南市以外的市。相同来源键合并，包数总和必须与品规最终支数按每包支数换算的包数完全一致。

### 7.8 完成批次

`POST /api/v1/scan-sessions/{session_id}/complete`

```json
{
  "confirm_exceptions": true
}
```

后端在事务中锁定批次和汇总行，校验至少有一个有效品规、数量按整包对齐、每个品规来源支数与最终支数完全一致。未识别或未解决歧义允许保留，但存在任一异常时 `confirm_exceptions` 必须为 `true`。通过后将 `DRAFT` 改为 `COMPLETED` 并写入 `completed_at`。完成后扫码、歧义处理及进行中批次的带原因调整接口继续拒绝；查询、导出以及第 7.8.1 节定义的结果修订接口保留。

#### 7.8.1 已完成盘点结果修订

- `GET /api/v1/product-options?query={名称或条码后6位}&page=1&page_size=20`：所有登录用户可查询启用品规，响应项精确包含 `id`、`carton_code`、`brand`、`standard_name`、`carton_retail_price`、`sticks_per_pack`、`packs_per_carton`。
- `POST /api/v1/scan-sessions/{session_id}/result-items`：向 `COMPLETED` 结果加入品规；请求包含 `request_id`、`product_id`、`quantity_cartons`、`source_allocations`。
- `PUT /api/v1/scan-sessions/{session_id}/result-items/{product_id}`：以完整数量和来源替换现有结果；请求不含 `product_id`，其余字段同上。
- 现有来源替换和删除接口允许用于权限范围内的 `COMPLETED` 结果；扫码及歧义接口不得放开。

`quantity_cartons` 最小为 `0.1` 且必须是 `0.1` 的整数倍；来源包数必须与该数量完全一致。管理员可修订全部结果，同县分局操作员可共同修订本分局结果，查看员返回 403，跨分局记录按不存在处理。新增、替换和删除均锁定批次及汇总行，使用唯一 `request_id` 幂等并追加 `ADJUST` 流水；不要求人工填写修订原因，系统自动记录动作、摘要、操作人和时间。修改后批次状态仍为 `COMPLETED`，Excel 每次根据数据库最新结果在内存中生成。

### 7.9 Excel 导出

`GET /api/v1/scan-sessions/{session_id}/export.xlsx`

返回 MIME 类型：

```text
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
```

仅已完成且含有效品规的批次可以导出。后端在内存中创建文件、写入一条 `export_records` 后直接返回文件字节，不创建服务器文件。

### 7.10 简道云登记快照与一键导入

- `GET /api/v1/scan-sessions/{session_id}/integration-snapshot`：查询当前批次快照和导入状态；未生成时返回 `snapshot: null`。
- `POST /api/v1/scan-sessions/{session_id}/jiandaoyun-import`：为已完成批次首次生成不可变快照并执行一次外部调用；明确失败时复用原快照人工重试。

两个接口均复用批次数据范围：管理员可访问全部批次，操作员只能访问本分局批次。POST 必须校验 Origin。成功后的重复 POST 返回原 `SUCCEEDED` 记录，不再次调用简道云；`PENDING` 和 `UNCERTAIN` 状态拒绝再次发送。

## 8. 错误码

| 错误码 | HTTP | 含义 |
|---|---:|---|
| `AUTH_REQUIRED` | 401 | 未登录或登录过期 |
| `FORBIDDEN` | 403 | 无操作权限 |
| `PRODUCT_NOT_FOUND` | 404 | 品规不存在 |
| `BARCODE_INVALID` | 422 | 编码不是 6～64 位纯数字 |
| `SCAN_UNKNOWN` | 200 | 未识别编码，业务结果而非系统异常 |
| `SCAN_AMBIGUOUS` | 200 | 编码存在多个候选品规 |
| `SCAN_SESSION_CLOSED` | 409 | 批次不是进行中状态 |
| `IDEMPOTENCY_CONFLICT` | 409 | 同一请求号对应不同请求内容 |
| `NEGATIVE_QUANTITY` | 422 | 调整后数量小于 0 |
| `SCAN_SESSION_ITEM_NOT_FOUND` | 404 | 当前批次不存在该品规汇总项 |
| `ADJUSTMENT_REASON_REQUIRED` | 422 | 未选择调整原因，或选择其他但未填写说明 |
| `SOURCE_LOCATION_INVALID` | 422 | 来源类型与省市不匹配 |
| `SOURCE_QUANTITY_MISMATCH` | 422 | 来源包数合计与品规最终数量不一致 |
| `QUANTITY_NOT_PACK_ALIGNED` | 422 | 最终支数无法换算为整包 |
| `SOURCE_ALLOCATION_REQUIRED` | 409 | 存在未完成来源拆分的品规 |
| `EXCEPTION_CONFIRMATION_REQUIRED` | 409 | 存在异常编码但未二次确认 |
| `EXPORT_SESSION_NOT_COMPLETED` | 409 | 批次尚未完成，不能导出 |
| `RESULT_SESSION_NOT_COMPLETED` | 409 | 当前批次不是已完成结果，不能调用结果修订接口 |
| `PRODUCT_INACTIVE` | 409 | 已停用品规不能加入盘点结果 |
| `IMPORT_VALIDATION_FAILED` | 422 | 导入文件未通过校验 |
| `EXPORT_EMPTY` | 422 | 批次没有可导出数据 |
| `INTEGRATION_NOT_CONFIGURED` | 409 | 真实外部接口尚未配置 |
| `INTEGRATION_SESSION_NOT_COMPLETED` | 409 | 批次尚未完成，不能导入简道云 |
| `INTEGRATION_EMPTY` | 422 | 批次没有可导入的有效品规 |
| `INTEGRATION_IN_PROGRESS` | 409 | 当前批次正在导入 |
| `INTEGRATION_UNCERTAIN` | 409 | 上次导入结果不确定，需要人工核查 |
| `INTEGRATION_EXTERNAL_REJECTED` | 502 | 简道云明确拒绝，允许人工重试原快照 |
| `INTEGRATION_EXTERNAL_UNCERTAIN` | 502/504 | 外部结果不确定，禁止直接重试 |

## 9. Excel 导出规格

### 9.1 工作表

| 工作表 | 主要字段 |
|---|---|
| 卷烟登记表 | 标识、承办单位、立案编号、累计扫描数量、累计零售价合计；品规名称、条形码、品牌、类型、条支比、零售价（条）、查获数量（条）、查获数量（支）、来源类型、来源省、来源市 |
| 品规汇总 | 品牌、品规名称、条形码、条支比、每包支数、零售价、最终包数、折合条数、总支数、参考金额 |
| 操作流水 | 时间、事件类型、结果、原始编码、品规、单位、变化支数、操作人、原因 |
| 异常编码 | 编码、异常类型、候选品规、发生时间、处理状态 |

### 9.2 格式

- 编码列使用文本格式；
- 来源拆分最小单位为包；条数显示一位小数，支数和包数显示整数；
- 金额使用两位小数；
- 日期显示为 `yyyy-mm-dd hh:mm:ss`；
- 首行冻结并启用筛选；
- 文件名为 `涉案卷烟统计_{session_no}_{yyyyMMdd_HHmmss}.xlsx`；
- 工作簿元数据记录模板版本和生成时间。
- 每次请求即时生成，服务器不保存导出文件实体；`export_records` 只保存审计元数据。

## 10. 简道云罚没烟登记规格

### 10.1 字段映射

主表映射：批次 `display_label` → 标识 ID，`branch_name` → 县（分）局，`filing_case_no` → 立案编号，原批次 `operator_name` → 登记人员。

子表对最终数量大于零的品规逐条码生成一行：`carton_code` → 条包装条形码，`standard_name` → 品规名称，`brand` → 品牌，类型固定“卷烟”，`sticks_per_carton` → 条支比，`total_sticks / sticks_per_carton` → 入库数量（条）。条码为 JSON string，条支比和条数为 JSON number；同名不同条码平级发送，来源地、价格、流水和异常编码不发送。

### 10.2 状态机

```text
未生成 → PENDING → SUCCEEDED
                → FAILED → PENDING（人工重试同一快照）
                → UNCERTAIN（人工核查，不允许直接重试）
```

首次点击保存不可变业务 `payload_json`，调用时再用运行环境中的应用 ID、表单 ID 和开关组装完整外部请求。成功后任何重复请求返回原外部数据 ID，不再次发送；成功后本系统结果修订不改变快照。HTTP 4xx 记为 `FAILED`，网络异常、超时、HTTP 5xx、2xx 非 JSON 或缺少 `data._id` 记为 `UNCERTAIN`。外部失败不得改变盘点结果。`PENDING` 超过 120 秒时转为 `UNCERTAIN`，用于收敛调用期间进程退出的状态，不自动再次发送。

### 10.3 HTTP 和安全

适配器使用 HTTPS、UTF-8 JSON 和 `Authorization: Bearer <API Key>`，连接超时 5 秒、读取超时 20 秒，单次人工操作不自动重试，不启动外部工作流或触发器。真实地址、应用 ID、表单 ID 和 API Key 由后端环境变量提供，不写入前端、数据库、日志或版本文件。控制器不得记录完整外部请求、响应或鉴权头。

### 10.4 页面

一键导入位于已完成盘点页面，与 Excel 导出平级。未导入显示可点击的“一键导入简道云”；处理中显示禁用的“正在导入…”；成功后原位置显示禁用的“已导入”，悬停提示“该盘点批次已经导入简道云，不能重复导入。”；明确失败显示“重新导入”；结果不确定显示禁用的“导入结果待核查”。页面刷新后从数据库恢复状态。

## 11. 权限规格

| 操作 | ADMIN | OPERATOR | VIEWER |
|---|:---:|:---:|:---:|
| 管理用户 | ✓ |  |  |
| 导入/维护品规 | ✓ |  |  |
| 新建和操作批次 | ✓ | ✓ |  |
| 完成/作废批次 | ✓ | ✓ |  |
| 查询已完成批次 | ✓ | ✓ | ✓ |
| 导出 Excel | ✓ | ✓ | ✓ |
| 查看审计日志 | ✓ |  |  |
| 一键导入简道云 | ✓ | ✓ |  |
| 配置真实接口 | ✓ |  |  |

## 12. 安全规格

- 密码使用 Argon2id 或等效强哈希；
- 会话放入 Secure、HttpOnly、SameSite Cookie；
- 对登录、导入和写接口实施合理限流；
- 所有输入经过 Pydantic 校验；
- Excel 上传限制扩展名、MIME、文件大小和最大行数；
- 导出文件只能通过授权接口下载；
- API 日志不得记录密码、Token 或完整外部鉴权信息；
- Nginx 设置安全响应头和请求体大小限制；
- 数据库账号遵循最小权限原则。

## 13. Docker 与配置

### 13.1 服务

```text
nginx  → depends_on api
api    → depends_on mysql
backup → depends_on mysql
mysql  → persistent volume
```

### 13.2 必需环境变量

```text
APP_ENV
DATABASE_URL
MYSQL_DATABASE
MYSQL_USER
MYSQL_PASSWORD
MYSQL_ROOT_PASSWORD
ALLOWED_ORIGINS
JIANDAOYUN_CREATE_URL
JIANDAOYUN_APP_ID
JIANDAOYUN_ENTRY_ID
JIANDAOYUN_API_KEY
```

生产环境不得提交真实 `.env`。仓库仅提供 `.env.example`。

### 13.3 健康检查

- Nginx：HTTP `/healthz`；
- API：`/api/v1/health/live` 和 `/api/v1/health/ready`；
- MySQL：`mysqladmin ping`；
- Ready 检查应包含数据库连接和当前模块必需表校验。

## 14. 日志、监控和备份

- 应用日志使用 JSON 格式并包含 `trace_id`；
- 记录请求方法、路径、耗时、状态码和用户编号，不记录敏感正文；
- 扫码业务结果写业务表，不能只依赖文本日志；
- MySQL 每日全量备份，备份文件记录校验值；
- 定期在隔离环境执行恢复验证；
- 导出文件和应用日志设置保留周期。

## 15. 测试规格

### 15.1 单元测试

- 条码/包码匹配；
- 未识别和歧义识别；
- 条、包、支换算；
- 金额计算；
- 幂等请求；
- 数量下限；
- 权限矩阵；
- 导入校验和 `-1` 包码清洗。

### 15.2 集成测试

- 扫码事务及汇总一致性；
- 并发提交相同和不同请求号；
- 完成批次与扫码竞争；
- Excel 导出与数据库汇总对账；
- 简道云不可变快照、成功防重、失败重试和不确定状态；
- 数据库初始化、结构一致性和备份恢复。

### 15.3 端到端测试

- 登录后新建批次并连续扫码；
- 成功、未知和歧义三种识别路径；
- 人工调整及原因校验；
- 完成批次后禁止继续扫码；
- 导出并校验四个工作表；
- 已完成批次的一键导入按钮及各状态提示；
- 不同角色页面和接口权限。

## 16. 需求追踪

| PRD 范围 | SPEC 实现章节 |
|---|---|
| 用户与权限 | 第 11、12 节 |
| 品规导入 | 第 5.2～5.5 节 |
| 扫描批次 | 第 5.6、7.2 节 |
| 扫码登记 | 第 5.7、6、7.3～7.5 节 |
| 汇总统计 | 第 5.8、6.3 节 |
| Excel 导出 | 第 7.7、9 节 |
| 简道云罚没烟登记 | 第 5.11、7.10、10 节 |
| 部署与运维 | 第 13、14 节 |
| 验收和质量 | 第 15 节 |

## 17. 完成定义

功能必须满足 PRD 验收场景；自动化测试通过；数据库初始化可在空库和已有兼容结构环境重复执行且不破坏数据；Docker Compose 能完成启动、健康检查、备份和恢复；OpenAPI 文档与实际接口一致；Excel 导出通过数据和格式检查；简道云真实调用经过专门测试批次验证且不会泄露配置或重复创建。
