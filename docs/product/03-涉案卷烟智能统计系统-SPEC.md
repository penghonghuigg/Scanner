# 涉案卷烟智能统计系统软件需求规格说明书（SPEC）

## 1. 适用范围

本文定义系统数据库、API、前端字段和核心业务规则。开发顺序以 `docs/plans/00-系统分阶段实施计划.md` 为准，一次只实现一个已批准阶段。

当前已实现登录、人员注册、五个分局、卷烟品规管理与导入、扫描批次与最小案件信息、扫码识别累计、异常处理和 MySQL 持久化；人工调整、完成批次、批次导出和罚没烟快照仍属于后续阶段。

## 2. 技术约束

- 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia、Vue Router；
- 后端：Python 3.12、FastAPI、Pydantic、SQLAlchemy 2.x；
- 数据库：MySQL 8.x、InnoDB、`utf8mb4`；
- API 前缀：`/api/v1`；
- 网关：Nginx；
- 部署：Windows Docker Desktop，最终统一 Docker Compose；
- 数据库初始化：SQLAlchemy metadata + 显式 `init_db`；
- 不使用 Alembic 或其他数据库迁移框架；
- 不引入 Redis、消息队列、微服务和 Kubernetes。

## 3. 通用契约

成功响应：

```json
{
  "success": true,
  "data": {},
  "trace_id": "请求追踪编号"
}
```

失败响应：

```json
{
  "success": false,
  "error": {
    "code": "BUSINESS_ERROR_CODE",
    "message": "面向用户的中文提示"
  },
  "trace_id": "请求追踪编号"
}
```

所有写接口必须验证登录状态、权限和允许的请求来源。错误响应不得包含堆栈、密码、Cookie 或数据库连接信息。

## 4. 枚举与公共字段

### 4.1 用户角色

```text
ADMIN
OPERATOR
VIEWER
```

`VIEWER` 仅为现有数据库兼容保留，当前人员注册接口只创建 `OPERATOR`。

### 4.2 分局

| `branch_code` | `branch_name` |
|---|---|
| `TIANDA` | 田大分局 |
| `XIEBA` | 谢八分局 |
| `PANJI` | 潘集分局 |
| `SHOUXIAN` | 寿县局 |
| `FENGTAI` | 凤台县局 |

管理员的 `branch_code` 和 `branch_name` 可以为 `null`，操作员必须属于一个有效分局。

### 4.3 授权规则

系统不定义权限字符串枚举，登录响应不返回 `permissions` 数组。

- `ADMIN` 可以注册人员、维护品规并操作全部分局业务；
- `OPERATOR` 可以操作本人所属分局且创建人不是管理员的批次；
- `VIEWER` 仅为已有数据库兼容保留，不开放创建入口，只读访问本人分局且创建人不是管理员的批次；
- `ADMIN` 创建并归属某县分局的批次只对管理员可见；
- 管理页面的前端路由直接检查 `role === "ADMIN"`；
- 所有接口仍在后端检查角色，后续批次接口同时检查 `branch_code`；
- 前端隐藏入口不是安全措施，后端校验结果为准。

### 4.4 时间和编码

- 数据库时间使用 UTC 的 `DATETIME(6)`；
- API 时间使用 ISO 8601 字符串；
- 前端按中国标准时间显示；
- 条码、包码、立案编号和批次编号均使用字符串；
- 金额使用 `DECIMAL(12,2)`，不得使用浮点类型。

## 5. 数据库模型

### 5.1 `users`（已实现）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键、自增 |
| `username` | VARCHAR(64) | 唯一登录账号 |
| `password_hash` | VARCHAR(255) | Argon2id 密码摘要 |
| `display_name` | VARCHAR(100) | 姓名 |
| `role` | VARCHAR(20) | ADMIN、OPERATOR、VIEWER |
| `branch_code` | VARCHAR(20) | 分局代码；管理员可空 |
| `is_active` | BOOLEAN | 是否可登录 |
| `created_at` | DATETIME(6) | 创建时间 |
| `updated_at` | DATETIME(6) | 更新时间 |

索引：`UNIQUE(username)`、`INDEX idx_users_branch(branch_code)`。

### 5.2 `user_sessions`（已实现）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键、自增 |
| `user_id` | BIGINT UNSIGNED | 用户 ID |
| `token_hash` | VARCHAR(64) | 唯一会话令牌摘要 |
| `expires_at` | DATETIME(6) | 过期时间 |
| `revoked_at` | DATETIME(6) | 退出时间，可空 |
| `created_at` | DATETIME(6) | 创建时间 |

浏览器仅保存 HttpOnly Cookie，不在 `localStorage` 保存登录密钥。

### 5.3 `cigarette_products`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `carton_code` | VARCHAR(64) | 当前品规版本唯一条码 |
| `pack_code` | VARCHAR(64) | 当前品规版本包码，可空、可重复 |
| `brand` | VARCHAR(100) | 品牌 |
| `standard_name` | VARCHAR(200) | 标准品规名称 |
| `carton_retail_price` | DECIMAL(12,2) | 每条参考零售价，可空 |
| `sticks_per_pack` | SMALLINT UNSIGNED | 每包支数 |
| `packs_per_carton` | SMALLINT UNSIGNED | 每条包数 |
| `is_active` | BOOLEAN | 是否启用 |
| `created_at` | DATETIME(6) | 创建时间 |
| `updated_at` | DATETIME(6) | 更新时间 |

一行代表一个具体品规版本。同名但条码不同的记录分别保存；条码使用唯一索引 `UNIQUE(carton_code)`；包码使用普通索引 `INDEX idx_products_pack_active(pack_code, is_active)`，不得设置唯一约束；品牌和名称使用 `INDEX idx_products_name(brand, standard_name)`。

`sticks_per_carton = sticks_per_pack × packs_per_carton`；`pack_retail_price = carton_retail_price ÷ packs_per_carton`，均由后端统一计算，金额使用 `DECIMAL` 并四舍五入保留两位小数。每条价格为空时每包价格也为空。

### 5.4 品规 Excel 映射与清洗

模板和现有文件列为：`条码`、`品规名称`、`包码`、`品牌`、`零售价格`、`包数量`、`条数量`。其中“零售价格”为每条参考零售价，“包数量”为每包支数，“条数量”为每条支数。

- 文件只接受 `.xlsx`，最大 10 MB、10,000 个数据行；
- 编码按字符串读取，只允许 6～64 位数字；
- `-1` 或空包码清洗为 `NULL`，`-1` 或空价格清洗为 `NULL`；
- `包数量 > 0` 且 `条数量 ÷ 包数量` 为正整数时，商作为每条包数；
- `包数量 = -1` 且无包码时，以条数量作为每包支数、每条包数为 1；
- `包数量 = -1` 但存在包码，或包装换算不是正整数时，该行拒绝导入；
- 同一文件重复条码的行拒绝导入；已存在条码执行更新；新条码新增版本；文件未出现的版本保持不变；
- 包码重复允许保存并动态标记歧义；包码与文件或数据库中的任意条码冲突时清洗为 `NULL` 并产生警告；
- 有效行在一个事务中新增或更新，错误行跳过；意外数据库错误时事务整体回滚。

### 5.5 `scan_sessions`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `session_no` | VARCHAR(40) | 唯一批次编号 |
| `business_type` | VARCHAR(32) | 业务类型 |
| `filing_case_no` | VARCHAR(100) | 立案编号，可空 |
| `location` | VARCHAR(200) | 地点，可空 |
| `notes` | VARCHAR(500) | 备注，可空 |
| `branch_code` | VARCHAR(20) | 所属分局 |
| `operator_id` | BIGINT UNSIGNED | 创建人 |
| `status` | VARCHAR(16) | DRAFT 或 COMPLETED |
| `completed_at` | DATETIME(6) | 完成时间，可空 |
| `created_at` | DATETIME(6) | 创建时间 |
| `updated_at` | DATETIME(6) | 更新时间 |

状态只能从 `DRAFT` 转为 `COMPLETED`。本期不提供重新打开和物理删除。

业务类型代码固定为 `MARKET_INSPECTION`（市场检查）、`DELIVERY_CHANNEL`（寄递渠道）、`SPECIAL_TRANSPORT`（专车运输）和 `OTHER`（其他）。阶段 4 只创建 `DRAFT` 批次。批次编号格式为 `PDyyyyMMdd-HHmmss-NNNN` 并设置唯一约束；索引为 `idx_scan_sessions_branch_status_created(branch_code, status, created_at)` 和 `idx_scan_sessions_operator_created(operator_id, created_at)`。

### 5.6 `scan_events`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `request_id` | CHAR(36) | 唯一幂等请求号 |
| `session_id` | BIGINT UNSIGNED | 扫描批次 |
| `event_type` | VARCHAR(24) | SCAN、RESOLVE、ADJUST |
| `result` | VARCHAR(24) | SUCCESS、UNKNOWN、AMBIGUOUS |
| `raw_code` | VARCHAR(64) | 原始编码，可空 |
| `product_id` | BIGINT UNSIGNED | 品规，可空 |
| `unit_type` | VARCHAR(16) | CARTON、PACK、STICK，可空 |
| `delta_sticks` | INT | 本次支数变化 |
| `source_event_id` | BIGINT UNSIGNED | RESOLVE 指向原 AMBIGUOUS 事件，可空 |
| `reason` | VARCHAR(500) | 调整原因，可空 |
| `candidate_snapshot` | JSON | 歧义候选，可空 |
| `product_snapshot` | JSON | 当时品规信息，可空 |
| `operator_id` | BIGINT UNSIGNED | 操作人 |
| `created_at` | DATETIME(6) | 创建时间 |

该表只追加，不提供更新原始扫码或物理删除接口。`request_id` 全局唯一；`source_event_id` 自引用 `scan_events.id` 并设置唯一约束，MySQL 允许多个 `NULL`，从数据库层保证一条歧义事件最多解决一次。

### 5.7 `scan_session_items`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `session_id` | BIGINT UNSIGNED | 批次 |
| `product_id` | BIGINT UNSIGNED | 品规 |
| `carton_count` | INT UNSIGNED | 条数 |
| `pack_count` | INT UNSIGNED | 包数 |
| `manual_delta_sticks` | INT | 人工调整支数 |
| `total_sticks` | INT UNSIGNED | 总支数 |
| `product_snapshot` | JSON | 品规快照 |
| `updated_at` | DATETIME(6) | 更新时间 |

约束：`UNIQUE(session_id, product_id)`，`total_sticks` 不得小于零。

### 5.8 `export_records`

保存批次 ID、文件名、模板版本、操作人和生成时间。导出文件按需生成，不要求长期保存文件副本。

### 5.9 `integration_snapshots`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT UNSIGNED | 主键 |
| `snapshot_no` | VARCHAR(40) | 唯一快照编号 |
| `session_id` | BIGINT UNSIGNED | 已完成批次，唯一 |
| `payload` | JSON | 不可变登记数据 |
| `created_by` | BIGINT UNSIGNED | 生成人 |
| `created_at` | DATETIME(6) | 生成时间 |

本期没有推送状态、重试次数、外部地址和响应日志字段。

## 6. 已实现认证 API

### 6.1 登录

`POST /api/v1/auth/login`

```json
{
  "username": "operator01",
  "password": "用户密码"
}
```

### 6.2 当前用户

`GET /api/v1/auth/me`

用户字段必须与前端 `AuthUser` 一致：

```json
{
  "id": 1,
  "username": "operator01",
  "display_name": "张三",
  "role": "OPERATOR",
  "branch_code": "FENGTAI",
  "branch_name": "凤台县局"
}
```

### 6.3 退出

`POST /api/v1/auth/logout`

撤销当前服务端会话并清除 Cookie。重复退出返回成功空数据。

### 6.4 注册操作员

`POST /api/v1/users`

```json
{
  "username": "operator01",
  "display_name": "张三",
  "branch_code": "FENGTAI",
  "password": "初始密码",
  "password_confirmation": "初始密码"
}
```

只有 `ADMIN` 可调用。后端固定创建 `OPERATOR`，请求不得包含 `role`。

### 6.5 登录模块精简边界

保留：`users`、`user_sessions`、Argon2id 密码摘要、HttpOnly Cookie、会话过期和撤销、允许来源校验、`trace_id`、五分局、登录/退出/当前用户/注册操作员接口。

删除：独立权限映射模块、权限字符串单元测试、登录响应中的 `permissions`、前端权限类型和权限路由元数据，以及工作台权限数量展示。

环境配置删除 `APP_SECRET_KEY`（当前代码未用于签名或加密）和 `VITE_API_BASE_URL`（前端始终使用同源 `/api/v1`）；删除未被代码读取的 `Settings.test_database_url` 字段，但保留测试脚本直接读取的 `TEST_DATABASE_URL`。同时删除前端从未使用的 `@` 路径别名及相关 Vite、TypeScript 配置。现有依赖包均有实际用途，本次不删除 Python 或 npm 依赖。

登录数据流保持不变：前端提交账号密码，后端校验 Argon2id 摘要并创建服务端会话，浏览器只接收 HttpOnly Cookie；刷新时调用 `/auth/me` 恢复用户；退出时撤销会话。错误码和统一响应信封保持不变。

实施采用 TDD：先修改后端、OpenAPI、前端契约和路由测试，使其因旧 `permissions` 字段或旧权限判断失败；再删除最小实现并运行登录、注册、路由守卫、静态检查和构建回归。

`VIEWER` 暂时保留只为避免修改已有 MySQL 表约束。当前代码和页面不新增查看员，也不围绕查看员开发额外功能。

## 7. 品规 API 与后续业务 API

| 方法与路径 | 用途 |
|---|---|
| `GET /api/v1/products` | 管理员分页查询品规版本 |
| `POST /api/v1/products` | 管理员单条新增品规版本 |
| `PATCH /api/v1/products/{id}` | 管理员编辑、停用或重新启用品规版本 |
| `GET /api/v1/products/import-template.xlsx` | 管理员下载带填写说明的导入模板 |
| `POST /api/v1/products/import` | 管理员导入品规 Excel，返回新增、更新、跳过、警告和问题明细 |
| `POST /api/v1/scan-sessions` | 新建扫描批次 |
| `GET /api/v1/scan-sessions` | 查询批次 |
| `GET /api/v1/scan-sessions/{id}` | 查询批次详情 |
| `POST /api/v1/scan-sessions/{id}/scan` | 扫码识别并累计 |
| `POST /api/v1/scan-sessions/{id}/resolve` | 处理歧义编码 |
| `GET /api/v1/scan-sessions/{id}/scan-state` | 查询权威汇总、流水和待处理歧义 |
| `POST /api/v1/scan-sessions/{id}/adjust` | 人工调整数量 |
| `POST /api/v1/scan-sessions/{id}/complete` | 完成批次 |
| `GET /api/v1/scan-sessions/{id}/export.xlsx` | 导出 Excel |
| `POST /api/v1/scan-sessions/{id}/snapshot` | 生成罚没烟登记快照 |

阶段 4 的三个批次接口和阶段 5 的 `/scan`、`/resolve`、`/scan-state` 已实现；`/adjust`、`/complete`、导出和快照接口仍只能在对应阶段批准后实现。

品规响应字段固定为：`id`、`carton_code`、`pack_code`、`brand`、`standard_name`、`carton_retail_price`、`pack_retail_price`、`sticks_per_pack`、`packs_per_carton`、`sticks_per_carton`、`is_pack_ambiguous`、`is_active`、`created_at`、`updated_at`。

查询支持名称、品牌、条码、包码、启用状态和包码歧义筛选。所有品规接口均要求登录和 `ADMIN` 角色；写接口继续校验允许来源。

模板包含“品规导入”和“填写说明”两个工作表，条码和包码列设置为文本。导入问题包含 Excel 行号、`ERROR` 或 `WARNING`、字段、错误码、说明、条码和品规名称；前端可将问题明细下载为 CSV，不保存导入任务或错误文件。

### 7.1 阶段 4 批次 API 契约

`POST /api/v1/scan-sessions` 请求仅接受 `business_type`、`filing_case_no`、`location`、`notes` 和可选 `branch_code`。管理员必须选择有效分局；操作员由后端强制使用本人分局；查看员不得新建。所有选填文本去除首尾空白，空字符串保存为 `null`。

`GET /api/v1/scan-sessions` 支持 `query`、`business_type`、`status`、`branch_code`、`page` 和 `page_size`；`query` 匹配批次编号、立案编号或地点。操作员和查看员只能返回本人分局且创建人不是管理员的批次，管理员可查询全部分局。

`GET /api/v1/scan-sessions/{id}` 在不存在或超出数据范围时统一返回 `SCAN_SESSION_NOT_FOUND`。

批次响应字段固定为：`id`、`session_no`、`business_type`、`business_type_name`、`filing_case_no`、`location`、`notes`、`branch_code`、`branch_name`、`operator_id`、`operator_name`、`status`、`status_name`、`completed_at`、`product_count`、`total_sticks`、`display_label`、`created_at`、`updated_at`。`product_count` 和 `total_sticks` 从 `scan_session_items` 动态汇总；`display_label` 由后端生成，格式为“日期—姓名—品规数量—总支数”。

### 7.2 阶段 5 扫码 API 契约

`POST /api/v1/scan-sessions/{id}/scan` 请求字段为 UUID 格式的 `request_id` 和恰好 13 位数字 `code`。同一请求号、批次和编码重放返回原事件、当前完整状态及 `idempotent_replay=true`；请求号复用于不同内容返回 `IDEMPOTENCY_CONFLICT`。前端输入达到 13 位后自动提交，尾随回车不重复触发；网络失败保留编码和请求号。数据库中已有 17 位品规不删除但不参与扫码，品规维护和 Excel 导入继续允许 6～64 位编码。

`POST /api/v1/scan-sessions/{id}/resolve` 请求字段为 `request_id`、原歧义 `event_id` 和候选 `product_id`。成功时不修改原事件，而是追加 `RESOLVE / SUCCESS / PACK` 事件。

`GET /api/v1/scan-sessions/{id}/scan-state` 返回：

- `summary`：`product_count`、`carton_count`、`pack_count`、`total_sticks`、`unknown_count`、`ambiguous_count`；
- `items`：全部品规汇总及扫描时的品规快照；
- `recent_events`：最近 50 条事件；
- `pending_ambiguities`：全部尚未解决的歧义事件及候选快照。

扫码和解决响应均返回 `event`、`state` 和 `idempotent_replay`。操作员只能写入权限范围内的 `DRAFT` 批次；查看员只能查询状态，不能扫码或解决歧义。成功、未知或歧义业务结果均使用 HTTP 200 返回，失败使用统一错误响应。

## 8. 扫码规则

### 8.1 识别结果

```text
无匹配       → UNKNOWN，不更新汇总
匹配一个品规 → SUCCESS，按条或包增加数量
匹配多个品规 → AMBIGUOUS，返回候选项，选择前不更新汇总
```

### 8.2 扫码事务

1. 使用行锁读取扫描批次；
2. 校验批次为 `DRAFT` 且用户有权限；
3. 查询 `request_id`，相同内容已存在则返回原结果，不重复计数；
4. 识别编码；
5. 成功时锁定或创建汇总行并更新数量；
6. 追加 `scan_events`；
7. 提交事务并返回后端最新汇总。

条码只允许唯一匹配；包码允许匹配多个启用品规并形成歧义候选。未识别编码只追加 `UNKNOWN` 事件，不提供人工绑定；管理员补充品规后必须使用新的 `request_id` 重新扫描。歧义解决必须从原事件候选快照中选择，并追加带 `source_event_id` 的解决事件。

### 8.3 数量换算

```text
扫码总支数 = 条数 × 每包支数 × 每条包数 + 包数 × 每包支数
最终总支数 = 扫码总支数 + 人工调整支数
```

最终总支数不得小于零。

## 9. Excel 规格

文件名：`涉案卷烟统计_{session_no}_{yyyyMMdd_HHmmss}.xlsx`。

| 工作表 | 内容 |
|---|---|
| 批次信息 | 批次编号、业务类型、立案编号、分局、操作人和完成时间 |
| 品规汇总 | 品牌、品规、条数、包数、总支数和参考金额 |
| 操作流水 | 时间、事件、编码、识别结果、数量变化、操作人和原因 |
| 异常编码 | 未识别或歧义编码、候选品规和处理结果 |

编码列设置为文本，数量设置为整数，金额保留两位小数，日期按中国标准时间显示。

## 10. 罚没烟登记快照规格

快照仅能从已完成批次生成，同一批次只保存一份。重复请求返回既有快照。载荷至少包含：

- 快照编号和版本；
- 批次编号、业务类型和立案编号；
- 所属分局、操作人和完成时间；
- 品规编码、名称、条数、包数和总支数；
- 生成时间。

本期不定义真实外部接口字段，不实现网络推送、自动重试或模拟推送。

## 11. 错误码

| 错误码 | HTTP | 含义 |
|---|---:|---|
| `AUTH_INVALID_CREDENTIALS` | 401 | 用户名或密码错误 |
| `AUTH_REQUIRED` | 401 | 未登录或会话过期 |
| `FORBIDDEN` | 403 | 无权限 |
| `ORIGIN_NOT_ALLOWED` | 403 | 请求来源不允许 |
| `VALIDATION_ERROR` | 422 | 请求字段不符合要求 |
| `USERNAME_EXISTS` | 409 | 登录账号已存在 |
| `BRANCH_INVALID` | 422 | 所属分局无效 |
| `PASSWORD_MISMATCH` | 422 | 两次密码不一致 |
| `BARCODE_INVALID` | 422 | 扫码编码不是恰好 13 位数字 |
| `PRODUCT_NOT_FOUND` | 404 | 品规版本不存在 |
| `CARTON_CODE_EXISTS` | 409 | 条码已属于其他品规版本 |
| `PACK_CODE_CONFLICT` | 409 | 手工填写的包码与条码冲突 |
| `IMPORT_FILE_INVALID` | 422 | Excel 类型、大小、表头或行数不符合要求 |
| `BUSINESS_TYPE_INVALID` | 422 | 批次业务类型无效 |
| `BRANCH_REQUIRED` | 422 | 管理员新建批次时未选择分局 |
| `SCAN_SESSION_NOT_FOUND` | 404 | 批次不存在或不在用户数据范围内 |
| `SCAN_SESSION_CREATE_FAILED` | 503 | 批次编号连续冲突导致创建失败 |
| `SCAN_SESSION_CLOSED` | 409 | 批次已完成 |
| `IDEMPOTENCY_CONFLICT` | 409 | 请求号与原请求内容冲突 |
| `SCAN_EVENT_NOT_FOUND` | 404 | 歧义事件不存在或不属于当前批次 |
| `AMBIGUITY_ALREADY_RESOLVED` | 409 | 歧义事件已经解决 |
| `AMBIGUITY_CANDIDATE_INVALID` | 422 | 所选品规不在原歧义候选中 |
| `NEGATIVE_QUANTITY` | 422 | 调整后数量小于零 |
| `UNRESOLVED_AMBIGUITY` | 409 | 存在未处理歧义 |
| `EXPORT_EMPTY` | 422 | 批次没有可导出数据 |

`UNKNOWN` 和 `AMBIGUOUS` 是扫码业务结果，不作为 HTTP 系统错误。

## 12. 数据库初始化和持久化

- `init_db` 只执行 `create_all` 创建缺失表并校验必要结构；
- 应用启动不执行 `init_db`；
- 已有表调整必须先备份、提供 SQL 并逐次取得用户确认；
- MySQL 使用命名卷 `scanner_mysql_data`；
- 禁止使用 `docker compose down -v` 删除业务数据；
- 测试数据库必须使用独立的 `scanner_test` 库。

## 13. 测试要求

- 后端：pytest 单元、API 和 MySQL 集成测试；
- 前端：Vitest 组件、状态和契约测试；
- 端到端：Playwright 验证主业务流程；
- 数据库字段、OpenAPI 模型和 TypeScript 类型必须一致；
- 每个业务模块遵循“契约 → 失败测试 → 数据库 → 后端 → 前端 → 联调 → 回归验证”。

## 14. 完成定义

当前阶段只有在范围内任务完成、适用测试和构建通过、字段契约一致、MySQL 持久化经过验证，且没有真实秘密和未授权 Git 操作时，才能声明完成。
