# 阶段 3：卷烟品规与 Excel 导入实现计划

> **面向 AI 代理的工作者：** 使用 executing-plans 在当前会话逐任务实施；严格遵循 TDD。仓库尚无首个提交，且用户要求不提交或推送，因此本计划不执行 Git 提交步骤。

**目标：** 交付管理员可用的单表品规版本管理，包括单条新增、查询编辑、停用启用、模板下载、现有 Excel 批量导入和错误结果下载。

**架构：** `cigarette_products` 一行代表一个具体品规版本，直接保存唯一条码和可选重复包码。FastAPI 服务层承担价格计算、冲突校验和导入事务，Vue 页面只展示后端权威结果并在浏览器生成问题 CSV。

**技术栈：** MySQL 8.x、SQLAlchemy 2.x、FastAPI、Pydantic、openpyxl、Vue 3、TypeScript、Vitest、pytest、Playwright。

---

## 需求映射与范围

- PRD：`FR-PROD-001` 至 `FR-PROD-009`。
- SPEC：`5.3`、`5.4`、`7`、`11`、`12`、`13`、`14`。
- 输入文件：`references/data/卷烟产品价格与规格表.xlsx`，只读，不覆盖。
- 范围外：扫描批次、扫码累计、异常处理、批次导出和罚没烟快照。

## 文件结构

- 创建 `backend/app/models/catalog.py`：单表 SQLAlchemy 模型。
- 创建 `backend/app/catalog/service.py`：新增、查询、编辑、价格与歧义业务规则。
- 创建 `backend/app/catalog/excel.py`：模板生成、Excel 解析、清洗与导入。
- 创建 `backend/app/schemas/catalog.py`：OpenAPI 请求与响应模型。
- 创建 `backend/app/api/v1/products.py`：五个管理员品规接口。
- 创建 `frontend/src/types/catalog.ts`、`frontend/src/api/products.ts`：前端契约与 API。
- 创建 `frontend/src/views/ProductManagementView.vue`：品规管理页面。
- 修改数据库初始化、路由、工作台、依赖和相关测试。

### 任务 1：数据库模型与初始化

**文件：**
- 创建：`backend/app/models/catalog.py`
- 修改：`backend/app/db/schema.py`
- 修改：`backend/tests/db/test_auth_metadata.py`
- 修改：`backend/tests/integration/test_init_db.py`
- 创建：`backend/tests/db/test_catalog_metadata.py`

- [ ] **步骤 1：编写失败的 MySQL 元数据测试**

测试必须断言真实 MySQL 元数据包含：

```python
assert set(columns) == {
    "id", "carton_code", "pack_code", "brand", "standard_name",
    "carton_retail_price", "sticks_per_pack", "packs_per_carton",
    "is_active", "created_at", "updated_at",
}
assert "carton_code" in unique_columns
assert "idx_products_pack_active" in indexes
assert "idx_products_name" in indexes
```

该测试应能抓住字段、唯一条码或包码索引缺失。

- [ ] **步骤 2：运行测试确认因表不存在而失败**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests\db\test_catalog_metadata.py -q
```

- [ ] **步骤 3：实现最小 SQLAlchemy 模型并纳入 metadata**

模型使用 MySQL 无符号整数、`DECIMAL(12,2)`、`DATETIME(6)`、InnoDB 和 `utf8mb4_0900_ai_ci`；不创建 `product_codes`。

- [ ] **步骤 4：更新初始化测试并验证只新增缺失表**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests\db backend\tests\integration\test_init_db.py -q
```

### 任务 2：品规领域规则与 CRUD 服务

**文件：**
- 创建：`backend/app/catalog/__init__.py`
- 创建：`backend/app/catalog/service.py`
- 创建：`backend/app/schemas/catalog.py`
- 创建：`backend/tests/unit/test_catalog_service.py`
- 创建：`backend/tests/integration/test_catalog_service_mysql.py`

- [ ] **步骤 1：编写价格、冲突和歧义失败测试**

```python
assert calculate_pack_price(Decimal("120.00"), 10) == Decimal("12.00")
assert calculate_pack_price(None, 10) is None
```

MySQL 测试分别证明：重复条码被拒绝、重复包码可保存且两行均返回歧义、包码等于任意条码时手工保存被拒绝、同名不同条码生成不同记录。

- [ ] **步骤 2：运行目标测试确认因服务缺失而失败**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests\unit\test_catalog_service.py backend\tests\integration\test_catalog_service_mysql.py -q
```

- [ ] **步骤 3：实现最小服务**

服务提供：

```python
create_product(session, payload)
update_product(session, product_id, payload)
list_products(session, query, is_active, ambiguous, page, page_size)
calculate_pack_price(carton_price, packs_per_carton)
```

所有写入使用事务；`pack_retail_price`、`sticks_per_carton`、`is_pack_ambiguous` 为响应计算字段。

- [ ] **步骤 4：运行领域与 MySQL 测试确认通过**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests\unit\test_catalog_service.py backend\tests\integration\test_catalog_service_mysql.py -q
```

### 任务 3：Excel 模板、解析与部分成功导入

**文件：**
- 修改：`backend/pyproject.toml`
- 创建：`backend/app/catalog/excel.py`
- 创建：`backend/tests/unit/test_catalog_excel.py`
- 创建：`backend/tests/integration/test_catalog_import_mysql.py`

- [ ] **步骤 1：编写失败的内存工作簿测试**

使用真实 openpyxl 工作簿字节验证：精确表头、文本编码、`-1` 清洗、价格清洗、正常换算、无包码单一包装、非法换算拒绝、重复条码拒绝、跨类型冲突清空包码并告警。

```python
assert result.created_count == 1
assert result.warning_count == 1
assert result.issues[0].level == "WARNING"
assert saved_product.pack_code is None
```

- [ ] **步骤 2：运行测试确认因 Excel 实现缺失而失败**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests\unit\test_catalog_excel.py backend\tests\integration\test_catalog_import_mysql.py -q
```

- [ ] **步骤 3：添加运行依赖并实现模板与导入**

添加 `openpyxl` 和 FastAPI 文件上传所需的 `python-multipart`。模板含“品规导入”“填写说明”；导入限制 `.xlsx`、10 MB、10,000 行。有效行新增或更新，错误行跳过，数据库异常整体回滚。

- [ ] **步骤 4：运行 Excel 与 MySQL 导入测试确认通过**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests\unit\test_catalog_excel.py backend\tests\integration\test_catalog_import_mysql.py -q
```

### 任务 4：管理员品规 API 与契约

**文件：**
- 创建：`backend/app/api/v1/products.py`
- 修改：`backend/app/api/v1/router.py`
- 修改：`backend/tests/api/test_openapi_contract.py`
- 创建：`backend/tests/api/test_products_api.py`

- [ ] **步骤 1：编写失败的 API 与 OpenAPI 测试**

覆盖五个接口、统一信封、管理员成功、操作员 403、未登录 401、写接口来源校验，以及响应字段与 SPEC 完全一致。

- [ ] **步骤 2：运行测试确认路由缺失导致失败**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests\api\test_products_api.py backend\tests\api\test_openapi_contract.py -q
```

- [ ] **步骤 3：实现最小 API 控制器**

控制器只处理 HTTP、鉴权和错误映射，业务规则调用 `catalog` 服务。模板返回正确 MIME 和中文文件名；导入返回问题明细。

- [ ] **步骤 4：运行后端完整测试与 Ruff**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests -q
backend\.venv\Scripts\ruff.exe check backend
```

### 任务 5：管理员品规页面

**文件：**
- 创建：`frontend/src/types/catalog.ts`
- 创建：`frontend/src/api/products.ts`
- 创建：`frontend/src/views/ProductManagementView.vue`
- 修改：`frontend/src/router/index.ts`
- 修改：`frontend/src/views/HomeView.vue`
- 创建：`frontend/src/styles/catalog.css`
- 创建：`frontend/src/__tests__/products-api.spec.ts`
- 创建：`frontend/src/__tests__/product-management-view.spec.ts`
- 修改：`frontend/src/__tests__/router-guard.spec.ts`
- 修改：`frontend/src/__tests__/contract.spec.ts`

- [ ] **步骤 1：编写失败的类型、API、路由和页面测试**

测试真实页面行为：管理员看到入口；操作员被退回首页；页面查询并展示价格和歧义文字；单条新增与编辑调用真实 API 客户端边界；导入显示统计；问题 CSV 对公式前缀字符进行安全处理。

- [ ] **步骤 2：运行目标测试确认页面和契约缺失而失败**

```powershell
npm.cmd --prefix frontend run test:unit -- --run src/__tests__/products-api.spec.ts src/__tests__/product-management-view.spec.ts src/__tests__/router-guard.spec.ts src/__tests__/contract.spec.ts
```

- [ ] **步骤 3：实现管理页面最小闭环**

页面包括统计区、搜索筛选、单条新增、编辑抽屉、停用确认、模板下载、文件导入、结果摘要和问题 CSV 下载。成功、失败、歧义和停用均使用文字而非只靠颜色。

- [ ] **步骤 4：运行前端完整测试、静态检查和构建**

```powershell
npm.cmd --prefix frontend run test:unit -- --run
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
```

### 任务 6：真实源文件、持久化与端到端验收

**文件：**
- 创建或修改：`tests/e2e/products.spec.ts`
- 只读使用：`references/data/卷烟产品价格与规格表.xlsx`

- [ ] **步骤 1：在测试库运行真实源文件导入验收**

断言总行数 5021，所有行均归入新增、更新或跳过，问题行具有可下载字段；源文件哈希在测试前后保持一致。

- [ ] **步骤 2：显式运行正式库 `init_db` 创建缺失表**

```powershell
backend\.venv\python.exe -m app.cli.init_db
```

该命令只允许创建缺失的 `cigarette_products`，不得调整现有认证表。

- [ ] **步骤 3：通过阶段 3 导入服务将参考 Excel 导入开发库**

导入后记录新增、更新、跳过和警告数量；不删除现有品规，不覆盖源 Excel。

- [ ] **步骤 4：重启 MySQL 后复查品规数量和代表性编码**

使用只读 SQL 检查持久化，不执行 `docker compose down -v`。

- [ ] **步骤 5：运行全量回归与 E2E**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests -q
backend\.venv\Scripts\ruff.exe check backend
npm.cmd --prefix frontend run test:unit -- --run
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
docker compose --env-file .env -f compose.dev.yaml config
```

## 实施结果（2026-08-27）

- 单表模型、领域规则、Excel 模板与部分成功导入、管理员 API 和前端管理页均已实施。
- 参考 Excel 共 5021 行：开发库新增 4982 条，跳过 39 条错误数据，2 条冲突包码已清空并告警。
- 后端 44 项、前端 18 项、端到端 3 项测试通过；Ruff、ESLint 和生产构建通过。
- MySQL 数据重新建立连接后仍为 4982 条；`compose.dev.yaml` 使用命名卷 `scanner_mysql_data` 持久化 `/var/lib/mysql`。
- 当前 Docker Desktop 安装未提供可调用的 `docker.exe`，未在本次验收中执行容器重启及 `docker compose config`；不影响已完成的业务实现，后续补齐 CLI 后可按本文命令复验。
- 未实现阶段 4 扫描批次及后续功能，未提交或推送 Git。

- [ ] **步骤 6：字段与范围审计**

核对 MySQL、OpenAPI、Pydantic 和 TypeScript 字段一致；确认没有 `product_codes`、`product_code`、扫描批次实现、真实秘密、提交或推送。
