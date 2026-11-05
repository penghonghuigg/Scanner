# 阶段 6+7：数量核对、来源拆分、完成批次与 Excel 导出实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `executing-plans` 在当前工作区逐任务执行本计划。所有步骤使用复选框跟踪。因当前工作区包含用户尚未提交的阶段 5 修改，不创建 worktree；未经用户明确要求，不执行 Git commit 或 push。

**目标：** 在现有扫码工作台中完成整包数量核对、来源地拆分、异常确认封存和四工作表 Excel 即时下载闭环。

**架构：** 继续使用 FastAPI + Vue + MySQL 单体应用。新增 `scan_item_source_allocations` 和 `export_records` 两张表，复用现有批次、汇总和只追加流水；地区目录由后端静态模块统一提供，Excel 使用 openpyxl 在内存中生成，不写服务器文件。

**技术栈：** Python 3.12、FastAPI、Pydantic、SQLAlchemy 2.x、MySQL 8.4、openpyxl、Vue 3、TypeScript、Element Plus、pytest、Vitest、Playwright。

---

## 1. 执行边界与基线

开始实施前必须确认：

- Docker Desktop 已启动，`mysql` 和 `nginx` 健康；
- 本机后端继续使用项目 `backend/.venv` 或用户的 `F:/anaconda/envs/phh/python.exe`；
- 当前 Git 工作区已有阶段 5 未提交修改，不覆盖、不回退、不重写这些修改；
- 不使用 Alembic；
- 应用启动不执行 DDL；
- 不执行 `docker compose down -v`；
- 新表 SQL 在实际执行前再次向用户展示并取得逐次批准；
- 本计划不包含单支调整、完成后重开、服务器保存 Excel、罚没烟快照或前后端容器化。

基线验证命令：

```powershell
Set-Location "C:\Users\彭鸿徽\Desktop\Demo"
docker compose --env-file .env -f compose.dev.yaml up -d --wait
docker compose --env-file .env -f compose.dev.yaml ps
backend\.venv\Scripts\pytest.exe backend\tests -q
npm.cmd --prefix frontend run test:unit -- --run
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
```

预期基线：后端至少保持阶段 5 的 86 项通过，前端至少 44 项通过，现有 Edge E2E 至少 4 项通过。若失败，停止本阶段实现并先按系统化调试流程确认是否为既有回归。

## 2. 文件结构

### 2.1 后端新增文件

- `backend/app/models/finalization.py`：来源分配和导出记录 SQLAlchemy 模型；
- `backend/app/schemas/finalization.py`：地区、来源分配、完成结果和导出记录契约；
- `backend/app/scanning/regions.py`：清理后的省市权威目录和来源规则校验；
- `backend/app/scanning/source_service.py`：来源分配查询、规范化、锁定和整体保存；
- `backend/app/scanning/completion_service.py`：完成前核验和批次封存；
- `backend/app/scanning/export_service.py`：四工作表内存 Excel 生成和导出记录；
- `backend/app/api/v1/finalization.py`：地区、来源、完成和 Excel 下载接口；
- `backend/scripts/sql/06_07_create_finalization_tables.sql`：两张新表的显式 MySQL DDL；
- `backend/tests/db/test_finalization_metadata.py`：模型结构测试；
- `backend/tests/unit/test_regions.py`：地区清理和来源校验测试；
- `backend/tests/unit/test_source_allocations.py`：换算、合并和数量匹配测试；
- `backend/tests/unit/test_excel_export.py`：工作簿结构和单元格格式测试；
- `backend/tests/integration/test_finalization_service_mysql.py`：来源、完成、并发和导出 MySQL 测试；
- `backend/tests/api/test_finalization_api.py`：接口、权限、错误码和下载测试。

### 2.2 后端修改文件

- `backend/app/db/schema.py`：导入新模型，使空库初始化和结构校验覆盖新表；
- `backend/app/api/v1/router.py`：挂载 finalization 路由；
- `backend/app/scanning/scan_service.py`：人工调整原因校验，并在所有写路径继续校验 DRAFT；
- `backend/app/schemas/scanning.py`：扩展数量调整请求原因字段；
- `backend/app/api/v1/scan_sessions.py`：映射新增调整原因错误码；
- `backend/app/core/errors.py`：把调整请求中缺少 `reason_type` 或无效 `OTHER` 说明的校验错误映射为 `ADJUSTMENT_REASON_REQUIRED`；
- `backend/tests/api/test_openapi_contract.py`：验证新增路径和字段；
- `backend/tests/api/test_scanning_api.py`：人工调整原因和完成后只读回归；
- `backend/tests/integration/test_scanning_service_mysql.py`：带原因调整和完成竞争测试；
- `backend/tests/integration/test_init_db.py`：新表初始化和幂等校验。

### 2.3 前端新增文件

- `frontend/src/components/scanning/SourceAllocationDrawer.vue`：来源分配抽屉；
- `frontend/src/components/scanning/AdjustmentReasonDialog.vue`：调整原因确认；
- `frontend/src/components/scanning/CompletionPanel.vue`：最终汇总、异常确认、完成和下载；
- `frontend/src/__tests__/source-allocation-drawer.spec.ts`：来源交互测试；
- `frontend/src/__tests__/adjustment-reason-dialog.spec.ts`：原因规则测试；
- `frontend/src/__tests__/completion-panel.spec.ts`：完成和下载状态测试。

### 2.4 前端修改文件

- `frontend/src/types/scanning.ts`：新增来源、地区、完成和调整原因类型；
- `frontend/src/api/scanSessions.ts`：新增来源、完成及二进制下载 API；
- `frontend/src/components/scanning/ProductQuantityTable.vue`：操作列增加来源入口，将直接调整改为请求确认；
- `frontend/src/views/ScanWorkspaceView.vue`：编排三个新组件并在完成后切换只读；
- `frontend/src/styles/scanning.css`：来源抽屉、确认弹窗和完成卡片样式；
- `frontend/src/__tests__/scan-sessions-api.spec.ts`：新增 API 契约和文件名解析测试；
- `frontend/src/__tests__/scan-workspace.spec.ts`：完整页面编排和只读回归；
- `tests/e2e/scan-sessions.spec.ts`：浏览器闭环和 Excel 下载测试。

### 2.5 文档修改文件

- `docs/product/01-涉案卷烟智能统计系统-技术方案.md`；
- `docs/product/02-涉案卷烟智能统计系统-PRD.md`；
- `docs/product/03-涉案卷烟智能统计系统-SPEC.md`；
- `docs/plans/00-系统分阶段实施计划.md`；
- `README.md`：只在新增数据库初始化命令或启动说明确有变化时同步。

## 3. API 与类型契约

### 3.1 地区和来源类型

```python
SourceType = Literal[
    "OUTSIDE_PROVINCE",
    "UNKNOWN",
    "LOCAL_HUAINAN",
    "ANHUI_OTHER_CITY",
]

class RegionCity(BaseModel):
    name: str

class RegionProvince(BaseModel):
    name: str
    cities: list[RegionCity]

class RegionCatalogPayload(BaseModel):
    source_types: list[SourceTypeOption]
    provinces: list[RegionProvince]
```

### 3.2 来源保存

```python
class SourceAllocationInput(BaseModel):
    source_type: SourceType
    province_name: str | None = None
    city_name: str | None = None
    pack_count: int = Field(gt=0)

class SourceAllocationReplaceRequest(BaseModel):
    items: list[SourceAllocationInput] = Field(min_length=1)

class SourceAllocationResponse(BaseModel):
    id: int
    source_type: SourceType
    source_type_name: str
    province_name: str | None
    city_name: str | None
    pack_count: int
    equivalent_cartons: str
    quantity_sticks: int

class ProductSourceAllocationState(BaseModel):
    product_id: int
    product_snapshot: ProductSnapshotResponse
    required_pack_count: int
    allocated_pack_count: int
    remaining_pack_count: int
    allocations: list[SourceAllocationResponse]
```

### 3.3 调整和完成

```python
AdjustmentReasonType = Literal[
    "ONSITE_VERIFICATION",
    "SCAN_CORRECTION",
    "LOOSE_PACK_VERIFICATION",
    "OTHER",
]

class CartonQuantityAdjustmentRequest(BaseModel):
    request_id: UUID
    operation: Literal["DELTA", "SET"]
    quantity: Decimal
    reason_type: AdjustmentReasonType
    reason_note: str | None = Field(default=None, max_length=200)

class CompleteScanSessionRequest(BaseModel):
    confirm_exceptions: bool = False

class CompletionSummaryResponse(BaseModel):
    scan_session: ScanSessionResponse
    summary: ScanSummaryResponse
    source_product_count: int
    source_allocated_product_count: int
    unknown_count: int
    unresolved_ambiguity_count: int
```

前端使用相同的字符串枚举和 snake_case 字段。`equivalent_cartons` 使用字符串，例如 `"15.0"`，避免契约中的浮点误差。

## 4. 明确数据库 SQL

`backend/scripts/sql/06_07_create_finalization_tables.sql` 必须精确包含以下 SQL。执行前先备份并再次取得用户批准。

```sql
CREATE TABLE IF NOT EXISTS scan_item_source_allocations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_item_id BIGINT UNSIGNED NOT NULL,
    source_type VARCHAR(32) NOT NULL,
    province_name VARCHAR(50) NULL,
    city_name VARCHAR(80) NULL,
    pack_count INT UNSIGNED NOT NULL,
    quantity_sticks INT UNSIGNED NOT NULL,
    source_key VARCHAR(200) NOT NULL,
    created_by BIGINT UNSIGNED NOT NULL,
    updated_by BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT uq_scan_item_source_allocations_item_key
        UNIQUE (session_item_id, source_key),
    CONSTRAINT ck_scan_item_source_allocations_type
        CHECK (source_type IN (
            'OUTSIDE_PROVINCE', 'UNKNOWN', 'LOCAL_HUAINAN', 'ANHUI_OTHER_CITY'
        )),
    CONSTRAINT ck_scan_item_source_allocations_quantity
        CHECK (pack_count > 0 AND quantity_sticks > 0),
    CONSTRAINT fk_scan_item_source_allocations_item
        FOREIGN KEY (session_item_id) REFERENCES scan_session_items(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_scan_item_source_allocations_created_by
        FOREIGN KEY (created_by) REFERENCES users(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_scan_item_source_allocations_updated_by
        FOREIGN KEY (updated_by) REFERENCES users(id)
        ON DELETE RESTRICT,
    INDEX idx_scan_item_source_allocations_item (session_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS export_records (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_id BIGINT UNSIGNED NOT NULL,
    filename VARCHAR(180) NOT NULL,
    file_size BIGINT UNSIGNED NOT NULL,
    file_sha256 CHAR(64) NOT NULL,
    template_version VARCHAR(20) NOT NULL,
    generated_by BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    CONSTRAINT fk_export_records_session
        FOREIGN KEY (session_id) REFERENCES scan_sessions(id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_export_records_generated_by
        FOREIGN KEY (generated_by) REFERENCES users(id)
        ON DELETE RESTRICT,
    INDEX idx_export_records_session_created (session_id, created_at, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

生产库备份与执行命令在用户批准 SQL 后使用：

```powershell
Set-Location "C:\Users\彭鸿徽\Desktop\Demo"
New-Item -ItemType Directory -Force backups | Out-Null
docker compose --env-file .env -f compose.dev.yaml exec -T mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction "$MYSQL_DATABASE" > /tmp/pre_stage_06_07.sql'
docker compose --env-file .env -f compose.dev.yaml cp mysql:/tmp/pre_stage_06_07.sql ./backups/pre_stage_06_07.sql
Get-Content -Raw backend/scripts/sql/06_07_create_finalization_tables.sql | docker compose --env-file .env -f compose.dev.yaml exec -T mysql sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'
docker compose --env-file .env -f compose.dev.yaml exec -T mysql sh -c 'exec mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" -e "SHOW CREATE TABLE scan_item_source_allocations; SHOW CREATE TABLE export_records;"'
```

`backups/` 必须保持 Git 忽略，不提交数据库备份。

## 5. 实施任务

### 任务 1：锁定模型和 OpenAPI 契约

**文件：**

- 创建：`backend/tests/db/test_finalization_metadata.py`
- 修改：`backend/tests/api/test_openapi_contract.py`
- 创建：`backend/app/models/finalization.py`
- 创建：`backend/app/schemas/finalization.py`
- 修改：`backend/app/db/schema.py`

- [ ] **步骤 1：先写模型失败测试**

```python
def test_finalization_metadata_contains_two_new_tables() -> None:
    assert "scan_item_source_allocations" in Base.metadata.tables
    assert "export_records" in Base.metadata.tables

def test_source_allocation_has_unique_item_source_key() -> None:
    table = Base.metadata.tables["scan_item_source_allocations"]
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("session_item_id", "source_key") in unique_columns
```

- [ ] **步骤 2：先写 OpenAPI 失败测试**

断言存在 `/api/v1/regions`、来源查询/保存、`/complete` 和 `/export.xlsx`，并断言调整请求精确包含 `reason_type`、`reason_note`。

- [ ] **步骤 3：运行并确认红灯**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/db/test_finalization_metadata.py backend/tests/api/test_openapi_contract.py -q
```

预期：新表、新 schema 或新路径不存在而失败。

- [ ] **步骤 4：实现最小模型和 Pydantic 类型**

模型字段、索引和约束必须与第 4 节 SQL 一致。`schema.py` 显式导入 `finalization`，但应用启动仍不调用 `initialize_database`。

- [ ] **步骤 5：运行模型测试**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/db/test_finalization_metadata.py -q
```

预期：PASS。OpenAPI 路径测试继续失败，留给后续路由任务。

### 任务 2：创建 SQL、备份和 MySQL 新表

**文件：**

- 创建：`backend/scripts/sql/06_07_create_finalization_tables.sql`
- 修改：`backend/tests/integration/test_init_db.py`

- [ ] **步骤 1：把第 4 节精确 SQL 写入脚本并运行静态检查**

```powershell
rg -n "CREATE TABLE IF NOT EXISTS|ON DELETE CASCADE|export_records|utf8mb4_0900_ai_ci" backend/scripts/sql/06_07_create_finalization_tables.sql
```

- [ ] **步骤 2：增加空测试库初始化失败测试**

测试必须断言两张新表可由 SQLAlchemy metadata 在空测试库创建，重复执行 `initialize_database` 不删除现有测试数据。

- [ ] **步骤 3：运行初始化回归测试**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/integration/test_init_db.py -q
```

预期：任务 1 已注册新模型，因此新增初始化断言直接 PASS；若失败，先修正模型导入或结构声明，不执行生产库 SQL。

- [ ] **步骤 4：暂停并向用户展示完整 SQL，取得生产开发库逐次批准**

没有明确批准时不得执行第 4 节生产库命令。

- [ ] **步骤 5：批准后先备份，再执行 SQL 和只读结构检查**

执行第 4 节 PowerShell 命令，保存 `SHOW CREATE TABLE` 输出作为证据；不得执行删除表、重建表或 `down -v`。

- [ ] **步骤 6：验证初始化和结构测试通过**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/integration/test_init_db.py backend/tests/db/test_finalization_metadata.py -q
```

### 任务 3：地区权威目录与来源校验

**文件：**

- 创建：`backend/app/scanning/regions.py`
- 创建：`backend/tests/unit/test_regions.py`
- 创建：`backend/app/api/v1/finalization.py`
- 修改：`backend/app/api/v1/router.py`
- 创建：`backend/tests/api/test_finalization_api.py`

- [ ] **步骤 1：写地区规则失败测试**

```python
def test_region_catalog_excludes_special_administrative_regions_and_duplicates():
    catalog = region_catalog()
    names = {(province.name, city) for province in catalog for city in province.cities}
    assert ("香港特别行政区", "香港特别行政区") not in names
    assert ("澳门特别行政区", "澳门特别行政区") not in names
    assert ("台湾省", "台湾省") in names
    assert len(names) == sum(len(province.cities) for province in catalog)

def test_validate_source_location_enforces_four_source_types():
    assert validate_source_location("LOCAL_HUAINAN", None, None) == (
        "安徽省", "淮南市"
    )
    with pytest.raises(SourceLocationInvalidError):
        validate_source_location("ANHUI_OTHER_CITY", "安徽省", "淮南市")
```

- [ ] **步骤 2：运行并确认红灯**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/unit/test_regions.py -q
```

- [ ] **步骤 3：实现清理后的地区常量和纯函数**

`region_catalog()` 返回确定顺序；`validate_source_location()` 返回规范化省市；`source_key()` 生成设计文档规定的唯一键。地区函数不访问数据库。

- [ ] **步骤 4：新增已鉴权 `GET /api/v1/regions` 和 API 测试**

测试 401 未登录、200 已登录、香港澳门缺失、四种来源类型齐全、安徽城市不含重复项。

- [ ] **步骤 5：运行地区和 API 定向测试**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/unit/test_regions.py backend/tests/api/test_finalization_api.py -q
```

### 任务 4：来源分配服务和接口

**文件：**

- 创建：`backend/app/scanning/source_service.py`
- 创建：`backend/tests/unit/test_source_allocations.py`
- 创建：`backend/tests/integration/test_finalization_service_mysql.py`
- 修改：`backend/app/api/v1/finalization.py`
- 修改：`backend/tests/api/test_finalization_api.py`

- [ ] **步骤 1：写换算和合并失败测试**

```python
def test_normalize_allocations_merges_same_source_and_converts_to_sticks():
    result = normalize_allocations(
        [
            allocation("OUTSIDE_PROVINCE", "天津市", "天津市", 2),
            allocation("OUTSIDE_PROVINCE", "天津市", "天津市", 3),
        ],
        sticks_per_pack=20,
    )
    assert len(result) == 1
    assert result[0].pack_count == 5
    assert result[0].quantity_sticks == 100
    assert result[0].equivalent_cartons == Decimal("0.5")
```

补充失败测试：包数为 0、非法省市、外省选择安徽、来源不详携带省市、总支数不匹配。

- [ ] **步骤 2：运行单元测试确认红灯**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/unit/test_source_allocations.py -q
```

- [ ] **步骤 3：实现无数据库的规范化和换算函数并转绿**

后端只接受整数 `pack_count`，`quantity_sticks = pack_count * product_snapshot["sticks_per_pack"]`，折合条数使用 `Decimal(pack_count) / Decimal(10)`。

- [ ] **步骤 4：写 MySQL 整体保存失败测试**

覆盖：权限范围、DRAFT 限制、批次行锁、品规行锁、完整替换、相同来源合并、调整后失配、删除品规级联来源和重启会话后仍可查询。

- [ ] **步骤 5：实现 `replace_source_allocations()` 和 `list_source_allocations()`**

服务首先调用现有 `get_scan_session()` 保证数据范围，再以 `SELECT ... FOR UPDATE` 锁定批次与汇总项。保存成功后提交并重新查询权威状态。

- [ ] **步骤 6：实现 GET/PUT API 和错误映射**

映射 `SOURCE_LOCATION_INVALID`、`SOURCE_QUANTITY_MISMATCH`、`SCAN_SESSION_ITEM_NOT_FOUND`、`SCAN_SESSION_CLOSED` 和 `FORBIDDEN`。

- [ ] **步骤 7：运行来源服务全链路定向测试**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/unit/test_source_allocations.py backend/tests/integration/test_finalization_service_mysql.py backend/tests/api/test_finalization_api.py -q
```

### 任务 5：带原因的整包调整

**文件：**

- 修改：`backend/app/schemas/scanning.py`
- 修改：`backend/app/scanning/scan_service.py`
- 修改：`backend/app/api/v1/scan_sessions.py`
- 修改：`backend/tests/integration/test_scanning_service_mysql.py`
- 修改：`backend/tests/api/test_scanning_api.py`

- [ ] **步骤 1：修改既有测试使其先失败**

所有人工调整请求增加：

```json
{
  "reason_type": "ONSITE_VERIFICATION",
  "reason_note": null
}
```

新增断言：缺少原因返回 `422 ADJUSTMENT_REASON_REQUIRED`；`OTHER` 没有说明被拒绝；成功流水原因分别为“现场核对修正”“其他：具体说明”。

- [ ] **步骤 2：运行调整测试确认红灯**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/integration/test_scanning_service_mysql.py -k adjustment -q
backend\.venv\Scripts\pytest.exe backend/tests/api/test_scanning_api.py -k adjustment -q
```

- [ ] **步骤 3：实现原因规范化和最小单位校验**

保留 `DELTA`/`SET` 和唯一 `request_id`；数量仍必须是 `0.1` 的整数倍，最终总支数必须是每包支数的整数倍。原因只写入新追加的 `ADJUST` 事件。

- [ ] **步骤 4：运行调整、删除和扫码回归**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/integration/test_scanning_service_mysql.py backend/tests/api/test_scanning_api.py -q
```

### 任务 6：完成批次服务和完成后只读

**文件：**

- 创建：`backend/app/scanning/completion_service.py`
- 修改：`backend/app/api/v1/finalization.py`
- 修改：`backend/tests/integration/test_finalization_service_mysql.py`
- 修改：`backend/tests/api/test_finalization_api.py`
- 修改：`backend/tests/api/test_scanning_api.py`

- [ ] **步骤 1：写完成规则失败测试**

覆盖以下精确场景：

```python
def test_complete_requires_every_product_source_total_to_match(): ...
def test_complete_requires_exception_confirmation_when_unknown_exists(): ...
def test_complete_allows_confirmed_unknown_and_unresolved_ambiguity(): ...
def test_complete_changes_status_and_completed_at(): ...
def test_complete_is_safe_when_repeated(): ...
def test_completed_session_rejects_scan_adjust_remove_source_and_resolve(): ...
```

- [ ] **步骤 2：运行完成测试确认红灯**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/integration/test_finalization_service_mysql.py -k complete -q
```

- [ ] **步骤 3：实现 `complete_scan_session()`**

在一个事务中按固定顺序锁定批次、全部 `scan_session_items` 和来源分配，重新计算有效品规数、总支数、未知数和未解决歧义数。没有有效品规返回 `EXPORT_EMPTY`；来源缺失返回 `SOURCE_ALLOCATION_REQUIRED`；异常未确认返回 `EXCEPTION_CONFIRMATION_REQUIRED`。

- [ ] **步骤 4：实现完成 API 并返回权威汇总**

重复调用已完成批次时，在权限校验后返回相同 `completed_at` 和当前汇总，不再次更新状态。

- [ ] **步骤 5：增加完成与扫码/调整竞争测试**

使用两个独立 MySQL Session 和线程屏障验证：完成成功后竞争写请求必须因 `COMPLETED` 被拒绝，不产生额外成功计数。

- [ ] **步骤 6：运行完成和全量扫码回归**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/integration/test_finalization_service_mysql.py backend/tests/integration/test_scanning_service_mysql.py backend/tests/api/test_scanning_api.py backend/tests/api/test_finalization_api.py -q
```

### 任务 7：四工作表 Excel 即时导出

**文件：**

- 创建：`backend/app/scanning/export_service.py`
- 创建：`backend/tests/unit/test_excel_export.py`
- 修改：`backend/app/api/v1/finalization.py`
- 修改：`backend/tests/integration/test_finalization_service_mysql.py`
- 修改：`backend/tests/api/test_finalization_api.py`

- [ ] **步骤 1：写工作簿失败测试**

```python
def test_export_workbook_has_exact_sheet_names():
    workbook_bytes = build_export_workbook(export_fixture())
    workbook = load_workbook(BytesIO(workbook_bytes), data_only=False)
    assert workbook.sheetnames == ["卷烟登记表", "品规汇总", "操作流水", "异常编码"]

def test_registration_rows_repeat_product_fields_and_include_sticks():
    sheet = exported_workbook()["卷烟登记表"]
    assert find_header(sheet, "查获数量（支）") is not None
    assert source_rows(sheet)[0]["品规名称"] == source_rows(sheet)[1]["品规名称"]

def test_codes_are_text_not_scientific_notation():
    cell = find_value_cell(exported_workbook()["卷烟登记表"], "6901028129756")
    assert cell.data_type == "s"
    assert cell.number_format == "@"
```

补充断言：四表字段、来源行完整重复、异常状态、金额两位小数、条数一位小数、支数整数、中国时间、冻结窗格、筛选、模板元数据和文件名。

- [ ] **步骤 2：运行单元测试确认红灯**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/unit/test_excel_export.py -q
```

- [ ] **步骤 3：实现纯内存 `build_export_workbook()`**

使用 `BytesIO` 和 openpyxl。函数输入为已序列化的不可变导出数据，不自行查询数据库，便于单元测试。

- [ ] **步骤 4：实现数据库快照读取和导出记录**

仅接受 `COMPLETED` 批次。生成 bytes 后计算 `len(content)` 和 `hashlib.sha256(content).hexdigest()`，写入 `export_records`；不创建目录、不调用文件写入 API。

- [ ] **步骤 5：实现下载 API**

返回 `Response(content=..., media_type=...)`，`Content-Disposition` 同时提供安全 ASCII fallback 与 UTF-8 文件名。进行中批次返回 `EXPORT_SESSION_NOT_COMPLETED`。

- [ ] **步骤 6：运行导出单元、集成和 API 测试**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/unit/test_excel_export.py backend/tests/integration/test_finalization_service_mysql.py backend/tests/api/test_finalization_api.py -q
```

### 任务 8：前端类型和 API 客户端

**文件：**

- 修改：`frontend/src/types/scanning.ts`
- 修改：`frontend/src/api/scanSessions.ts`
- 修改：`frontend/src/__tests__/scan-sessions-api.spec.ts`

- [ ] **步骤 1：写 API 客户端失败测试**

断言准确请求：

```text
GET  /api/v1/regions
GET  /api/v1/scan-sessions/18/source-allocations
PUT  /api/v1/scan-sessions/18/items/42/source-allocations
POST /api/v1/scan-sessions/18/complete
GET  /api/v1/scan-sessions/18/export.xlsx
```

下载测试模拟 blob 和 `Content-Disposition`，断言返回 `{ blob, filename }`，且 JSON API 仍由 `apiRequest()` 处理。

- [ ] **步骤 2：运行测试确认红灯**

```powershell
npm.cmd --prefix frontend run test:unit -- --run src/__tests__/scan-sessions-api.spec.ts
```

- [ ] **步骤 3：增加与后端一致的 TypeScript 类型和 API 函数**

调整请求增加 `reason_type`、`reason_note`。来源数量使用整数包，`equivalent_cartons` 使用字符串。

- [ ] **步骤 4：运行 API 和契约测试转绿**

```powershell
npm.cmd --prefix frontend run test:unit -- --run src/__tests__/scan-sessions-api.spec.ts src/__tests__/contract.spec.ts
```

### 任务 9：来源分配抽屉

**文件：**

- 创建：`frontend/src/components/scanning/SourceAllocationDrawer.vue`
- 创建：`frontend/src/__tests__/source-allocation-drawer.spec.ts`
- 修改：`frontend/src/components/scanning/ProductQuantityTable.vue`
- 修改：`frontend/src/views/ScanWorkspaceView.vue`
- 修改：`frontend/src/styles/scanning.css`

- [ ] **步骤 1：写组件失败测试**

覆盖：

- 外省流入显示省市并排除安徽；
- 来源不详隐藏省市；
- 市内串码锁定安徽省淮南市；
- 省内市外只列安徽非淮南城市；
- 包数为正整数；
- 相同来源在本地合并；
- 分配不足或超量时禁用保存并显示差额；
- 完成批次只允许查看。

- [ ] **步骤 2：运行测试确认红灯**

```powershell
npm.cmd --prefix frontend run test:unit -- --run src/__tests__/source-allocation-drawer.spec.ts
```

- [ ] **步骤 3：实现抽屉和权威保存流程**

组件只维护未保存表单草稿；保存成功后以 API 返回结果覆盖草稿。关闭或取消不修改后端。工作台加载时并行获取地区和来源状态。

- [ ] **步骤 4：在品规操作列增加来源入口**

不新增表格列、不恢复横向滚动。DRAFT 显示“来源分配”和“删除”；COMPLETED 显示“查看来源”。

- [ ] **步骤 5：运行来源和表格回归**

```powershell
npm.cmd --prefix frontend run test:unit -- --run src/__tests__/source-allocation-drawer.spec.ts src/__tests__/scan-workspace.spec.ts
```

### 任务 10：调整原因、完成确认和下载 UI

**文件：**

- 创建：`frontend/src/components/scanning/AdjustmentReasonDialog.vue`
- 创建：`frontend/src/components/scanning/CompletionPanel.vue`
- 创建：`frontend/src/__tests__/adjustment-reason-dialog.spec.ts`
- 创建：`frontend/src/__tests__/completion-panel.spec.ts`
- 修改：`frontend/src/components/scanning/ProductQuantityTable.vue`
- 修改：`frontend/src/views/ScanWorkspaceView.vue`
- 修改：`frontend/src/styles/scanning.css`
- 修改：`frontend/src/__tests__/scan-workspace.spec.ts`

- [ ] **步骤 1：写调整原因失败测试**

断言所有增加、减少和设置操作先打开原因弹窗；取消不调用 API；其他原因没有说明不能提交；失败重试复用原 `request_id`。

- [ ] **步骤 2：写完成面板失败测试**

断言汇总、来源进度、未知数和歧义数正确；来源不完整时按钮禁用；异常存在时必须勾选；完成成功切换只读；导出只在 COMPLETED 显示。

- [ ] **步骤 3：运行测试确认红灯**

```powershell
npm.cmd --prefix frontend run test:unit -- --run src/__tests__/adjustment-reason-dialog.spec.ts src/__tests__/completion-panel.spec.ts src/__tests__/scan-workspace.spec.ts
```

- [ ] **步骤 4：实现原因弹窗和工作台编排**

`ProductQuantityTable` 只发出待确认调整意图，`ScanWorkspaceView` 在原因确认后调用后端。成功后刷新扫码状态、来源状态和流水。

- [ ] **步骤 5：实现完成面板和确认弹窗**

完成成功后同时更新 `session` 与 `state`，清除输入焦点和编辑状态。未知或歧义存在时向 API 发送 `confirm_exceptions: true`。

- [ ] **步骤 6：实现浏览器下载**

API 返回 blob 后创建临时 object URL，触发带后端文件名的 `<a download>`，随后调用 `URL.revokeObjectURL()`；不保存业务数据到 localStorage。

- [ ] **步骤 7：运行前端定向测试**

```powershell
npm.cmd --prefix frontend run test:unit -- --run src/__tests__/adjustment-reason-dialog.spec.ts src/__tests__/completion-panel.spec.ts src/__tests__/scan-workspace.spec.ts
```

### 任务 11：浏览器闭环与文档同步

**文件：**

- 修改：`tests/e2e/scan-sessions.spec.ts`
- 修改：`docs/product/01-涉案卷烟智能统计系统-技术方案.md`
- 修改：`docs/product/02-涉案卷烟智能统计系统-PRD.md`
- 修改：`docs/product/03-涉案卷烟智能统计系统-SPEC.md`
- 修改：`docs/plans/00-系统分阶段实施计划.md`

- [ ] **步骤 1：扩展 E2E 场景并确认失败**

浏览器测试使用唯一测试批次完成：

```text
登录
→ 新建批次
→ 扫描条码和包码
→ 录入一个未知或歧义编码
→ 以 0.1 条调整并填写原因
→ 按两个来源拆分同一品规
→ 异常二次确认完成
→ 验证工作台只读
→ 下载 Excel
→ 验证下载文件名、MIME 类型和非空 `.xlsx` 内容
```

工作簿内部四张表和文本条码由任务 7 的 openpyxl 单元及 API 测试负责精确验证，浏览器测试不启动额外 Python 子进程。

- [ ] **步骤 2：运行 E2E 新场景确认红灯**

```powershell
npm.cmd --prefix frontend run test:e2e -- --grep "来源拆分完成并导出"
```

- [ ] **步骤 3：同步四份产品与计划文档**

必须明确修正：阶段 6+7 合并、整包最小单位、来源表、异常可确认完成、无 `version` 请求字段、四工作表、支数列、Excel 不落盘、罚没烟仍为范围外。

- [ ] **步骤 4：运行契约和 E2E 测试转绿**

```powershell
backend\.venv\Scripts\pytest.exe backend/tests/api/test_openapi_contract.py -q
npm.cmd --prefix frontend run test:e2e -- --grep "来源拆分完成并导出"
```

### 任务 12：全量验证、持久化和交付检查

**文件：**

- 不新增实现文件；只记录测试和审查证据。

- [ ] **步骤 1：运行后端全量测试和静态检查**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests -q
backend\.venv\Scripts\ruff.exe check backend
```

- [ ] **步骤 2：运行前端全量测试、Lint 和构建**

```powershell
npm.cmd --prefix frontend run test:unit -- --run
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

- [ ] **步骤 3：运行完整浏览器回归**

```powershell
npm.cmd --prefix frontend run test:e2e
```

- [ ] **步骤 4：验证 Compose 和 MySQL 持久化**

```powershell
docker compose --env-file .env -f compose.dev.yaml config --quiet
docker volume inspect scanner_mysql_data
docker compose --env-file .env -f compose.dev.yaml restart mysql nginx
docker compose --env-file .env -f compose.dev.yaml ps
```

重启前记录一个 DRAFT 来源分配和一个 COMPLETED 批次编号；重启后通过 API 或只读 SQL 验证来源、完成状态和 `export_records` 仍存在。不得使用 `down -v`。

- [ ] **步骤 5：检查字段契约**

逐项对照 OpenAPI、Pydantic、TypeScript 和实际响应：来源枚举、省市空值、整数包数/支数、字符串折合条数、完成异常计数和文件名。

- [ ] **步骤 6：检查工作区和秘密**

```powershell
git diff --check
git status --short
git diff --stat
git diff -- . ':(exclude).codex/**'
```

确认 `.env`、备份、数据库文件、导出文件、日志和真实密码未进入 Git；`.codex/` 保持忽略；`references/` 未被修改或删除。

- [ ] **步骤 7：提交交付报告但不提交 Git**

报告必须列出：实际修改文件、DDL 执行及备份证据、测试数量和命令、字段对照、持久化证据、未完成事项和 Git diff。等待用户确认后再决定是否 commit/push。

## 6. 验收矩阵

| 需求 | 主要任务 | 验收证据 |
|---|---|---|
| 0.1 条整包调整且带原因 | 任务 5、10 | API、事件原因、UI 弹窗测试 |
| 来源四分类和省市规则 | 任务 3、4、9 | 地区单测、MySQL、组件测试 |
| 同品规多来源拆分 | 任务 4、7、9 | 来源表和 Excel 多行测试 |
| 来源合计等于最终数量 | 任务 4、6 | 单元、集成和完成拒绝测试 |
| 未知/歧义确认后完成 | 任务 6、10 | API 和 E2E 二次确认 |
| 完成后只读 | 任务 6、10 | 所有写接口和页面状态测试 |
| 四工作表 Excel | 任务 7、11 | openpyxl 单元和下载 E2E |
| 编码不为科学计数法 | 任务 7 | `data_type == "s"`、`number_format == "@"` |
| 文件不保存服务器 | 任务 7、12 | 无文件写入代码和工作区检查 |
| 导出记录 | 任务 7 | 文件大小、SHA-256 与数据库一致 |
| 权限和分局隔离 | 任务 4、6、7 | ADMIN/OPERATOR/VIEWER API 测试 |
| MySQL 持久化 | 任务 2、12 | 容器重启前后只读核验 |

## 7. 实施检查点

实施分为三个审查检查点：

1. **数据库检查点：** 完成任务 1 的模型测试和 SQL 文件后，暂停，向用户展示 SQL 并取得执行批准；
2. **后端检查点：** 完成任务 2～7 后，报告后端、MySQL 和 Excel 定向测试证据；
3. **最终检查点：** 完成任务 8～12 后，报告全量验证和 Git diff，不提交或推送。

## 8. 本次实施结果（2026-09-02）

- 已按批准 SQL 创建并校验 `scan_item_source_allocations`、`export_records`，未修改或重建现有表；
- 已实现带原因的 0.1 条调整、来源目录与拆分、完成校验、异常二次确认、完成后只读和 Excel 内存下载；
- 已实现卷烟登记表、品规汇总、操作流水、异常编码四个工作表及导出审计元数据；
- 后端全量测试 134 项通过，Ruff 通过；前端单元测试 46 项通过，ESLint 和生产构建通过；
- Playwright 2 项通过，2 项因未提供临时 E2E 管理员凭据而跳过；
- MySQL 结构校验覆盖 8 张当前业务表，两次独立连接读取的新表记录数一致；
- 当前命令环境无法找到 Docker CLI，因此未执行 Compose 配置解析、卷检查和容器重启；已确认本机 3306、8080、8000、5173 端口可连接，Compose 文件仍使用命名卷 `scanner_mysql_data`；
- 未执行 Git 提交或推送。
