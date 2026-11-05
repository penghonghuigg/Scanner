# 简道云接口联调 Demo 实施计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `executing-plans` 在当前会话逐任务实施；严格执行测试驱动开发。未经用户确认，不执行 Git 提交或推送。

**目标：** 实现一个默认不联网、只有显式传入 `--send` 才会向简道云创建一条测试数据的 Python 联调 Demo，并在不泄露 API Key 的前提下验证请求和响应格式。

**架构：** 将请求构造、鉴权、响应解析和 HTTP 调用放在独立集成模块中，命令行脚本只负责读取环境变量、解析参数和显示脱敏结果。自动化测试全部使用 Mock；真实接口仅在所有测试通过后执行一次，且测试标识明确可删除。

**技术栈：** Python 3.12、httpx 0.28、pytest 8、Ruff。

---

## 文件结构

- 创建 `backend/app/integrations/__init__.py`：集成模块包标识。
- 创建 `backend/app/integrations/jiandaoyun_demo.py`：配置对象、请求体构造、鉴权头、HTTP 请求和响应解析。
- 创建 `backend/scripts/test_jiandaoyun_create.py`：默认 dry-run、显式 `--send` 的命令行入口。
- 创建 `backend/tests/unit/test_jiandaoyun_demo.py`：请求契约、安全边界、HTTP 分支和命令行行为测试。
- 修改 `.env.example`：增加无秘密的简道云配置说明，API Key 保持空值。
- 修改 `docs/plans/08-简道云接口联调Demo设计.md`：如实现中发现措辞偏差，仅同步已经验证的运行命令，不扩展正式推送功能。

## 范围边界

- 不增加前端按钮、API 路由或数据库表。
- 不读取盘点批次，不发送真实卷烟数据。
- 不实现自动重试、自动删除、工作流触发或智能助手触发。
- 不把用户在对话中提供的 API Key 写入文件、命令、日志或测试数据。
- 如果执行环境没有 `JIANDAOYUN_API_KEY`，在真实联调检查点停止并报告，不从对话内容拼接密钥。

### 任务 1：请求契约与脱敏配置

**文件：**
- 创建：`backend/app/integrations/__init__.py`
- 创建：`backend/app/integrations/jiandaoyun_demo.py`
- 测试：`backend/tests/unit/test_jiandaoyun_demo.py`

- [ ] **步骤 1：编写请求体和鉴权失败测试**

测试固定时间 `2026-09-04 12:00:00`，断言：

```python
payload = build_demo_payload(
    app_id="test-app-id",
    entry_id="test-entry-id",
    now=datetime(2026, 9, 4, 12, 0, 0),
)

assert payload["data"]["_widget_1788244617469"]["value"] == (
    "接口连通性测试-可删除-20260904-120000"
)
assert payload["data"]["_widget_1788244617471"]["value"][0][
    "_widget_1788247452468"
]["value"] == 0.1
assert build_authorization("secret") == "Bearer secret"
assert build_authorization("Bearer secret") == "Bearer secret"
```

同时断言全部 4 个主表字段和 6 个子表字段存在，`条支比` 与 `入库数量（条）` 是 JSON number，两个触发开关均为 `False`，空白 API Key 被拒绝。

- [ ] **步骤 2：运行测试并确认正确失败**

运行：

```powershell
backend\.venv\Scripts\pytest.exe backend\tests\unit\test_jiandaoyun_demo.py -q
```

预期：FAIL，原因是 `app.integrations.jiandaoyun_demo` 尚不存在。

- [ ] **步骤 3：实现最小请求构造代码**

实现不可变配置对象和以下接口：

```python
@dataclass(frozen=True)
class JianDaoYunConfig:
    create_url: str
    app_id: str
    entry_id: str
    api_key: str


def build_authorization(api_key: str) -> str: ...


def build_demo_payload(
    *, app_id: str, entry_id: str, now: datetime | None = None
) -> dict[str, object]: ...
```

请求体严格使用设计文档中的 widget ID 和 `{\"value\": ...}` 结构，不加入未获批准字段。

- [ ] **步骤 4：运行单元测试确认通过**

运行同步骤 2；预期：请求契约相关测试 PASS。

### 任务 2：HTTP 调用、成功判定与错误收敛

**文件：**
- 修改：`backend/app/integrations/jiandaoyun_demo.py`
- 修改：`backend/tests/unit/test_jiandaoyun_demo.py`

- [ ] **步骤 1：编写 Mock HTTP 失败测试**

使用 `httpx.MockTransport` 覆盖：

```python
result = create_demo_record(config, transport=transport, now=fixed_now)
assert result.data_id == "external-data-id"
assert result.test_identifier == "接口连通性测试-可删除-20260904-120000"
```

并分别断言 HTTP 非 2xx、2xx 非 JSON、2xx 缺少 `data._id`、连接超时均抛出自定义 `JianDaoYunDemoError`；异常消息不得包含 API Key、完整 Authorization 头或完整请求体。

- [ ] **步骤 2：运行测试并确认正确失败**

运行任务 1 的测试命令；预期：FAIL，原因是 HTTP 调用和响应类型尚未实现。

- [ ] **步骤 3：实现单次 HTTP 请求**

实现：

```python
@dataclass(frozen=True)
class CreateResult:
    data_id: str
    test_identifier: str
    created_at: str | None


class JianDaoYunDemoError(RuntimeError):
    pass


def create_demo_record(
    config: JianDaoYunConfig,
    *,
    transport: httpx.BaseTransport | None = None,
    now: datetime | None = None,
) -> CreateResult: ...
```

请求采用连接 5 秒、读取 20 秒超时；只调用一次 `POST`，不重试。错误只保留状态码、错误类型和最多 500 个字符的服务端响应，不输出请求头。

- [ ] **步骤 4：运行测试确认通过**

运行任务 1 的测试命令；预期：全部 PASS，且 Mock 收到一次 POST。

### 任务 3：安全的命令行入口

**文件：**
- 创建：`backend/scripts/test_jiandaoyun_create.py`
- 修改：`backend/tests/unit/test_jiandaoyun_demo.py`
- 修改：`.env.example`

- [ ] **步骤 1：编写 dry-run 与 `--send` 失败测试**

通过调用脚本的 `main(argv, environ, sender)` 断言：

```python
assert main([], environ={}, sender=sender) == 0
sender.assert_not_called()

assert main(["--send"], environ={}, sender=sender) != 0
sender.assert_not_called()
```

再断言配置齐全时 `--send` 只调用一次 sender；标准输出只包含目标主机、app ID、entry ID、测试标识和外部数据 ID，不包含传入的 API Key。

- [ ] **步骤 2：运行测试并确认正确失败**

运行任务 1 的测试命令；预期：FAIL，原因是命令行入口尚不存在。

- [ ] **步骤 3：实现参数解析和环境变量读取**

脚本暴露：

```python
def main(
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
    sender: Callable[..., CreateResult] = create_demo_record,
) -> int: ...
```

默认地址、app ID、entry ID 使用已批准的公开配置；真实发送必须存在非空 `JIANDAOYUN_API_KEY`。dry-run 打印格式化后的脱敏 JSON，但 Authorization 不进入打印对象。

在 `.env.example` 增加：

```dotenv
JIANDAOYUN_CREATE_URL=<真实地址仅写入本机环境>
JIANDAOYUN_APP_ID=<真实应用 ID 仅写入本机环境>
JIANDAOYUN_ENTRY_ID=<真实表单 ID 仅写入本机环境>
JIANDAOYUN_API_KEY=
```

- [ ] **步骤 4：运行目标测试和 dry-run**

运行：

```powershell
backend\.venv\Scripts\pytest.exe backend\tests\unit\test_jiandaoyun_demo.py -q
backend\.venv\python.exe backend\scripts\test_jiandaoyun_create.py
```

预期：测试 PASS；dry-run 退出码为 0、输出字段映射且不联网。

### 任务 4：静态检查、回归测试与秘密扫描

**文件：**
- 校验：本计划列出的全部代码和文档文件

- [ ] **步骤 1：运行 Ruff 和本阶段测试**

```powershell
backend\.venv\Scripts\ruff.exe check backend
backend\.venv\Scripts\pytest.exe backend\tests\unit\test_jiandaoyun_demo.py -q
```

预期：全部通过。

- [ ] **步骤 2：运行后端完整回归测试**

```powershell
backend\.venv\Scripts\pytest.exe backend\tests -q
```

预期：全部通过；若 MySQL 测试库未启动，先启动既有 MySQL 容器，不创建或修改业务表。

- [ ] **步骤 3：验证 dry-run 无网络副作用**

用 Mock sender 再次执行默认入口，确认调用次数为 0；人工检查输出不含 `Authorization`、`Bearer` 或 API Key。

- [ ] **步骤 4：扫描新增文件中的秘密和格式问题**

```powershell
rg -n "JIANDAOYUN_API_KEY=.+" backend .env.example
git diff --check
git status --short
```

预期：没有非空 API Key 配置命中；再人工检查新增 diff 中没有高熵密钥或完整鉴权头；`.env.example` 的 API Key 为空；仅报告工作区现有改动，不清理用户文件。

### 任务 5：唯一一次真实接口联调

**文件：**
- 不修改仓库文件

- [ ] **步骤 1：执行发送前检查点**

必须同时满足：目标测试、Ruff、后端回归和 dry-run 已通过；目标主机、app ID、entry ID 与批准设计一致；当前进程环境中已有 `JIANDAOYUN_API_KEY`。

若环境变量不存在，停止并请用户在自己的 PowerShell 会话中临时设置后运行；不得把对话中的密钥复制进工具命令或仓库文件。

- [ ] **步骤 2：只发送一次**

```powershell
backend\.venv\python.exe backend\scripts\test_jiandaoyun_create.py --send
```

预期：只创建 1 条以 `接口连通性测试-可删除-` 开头的记录。命令不得自动重试。

- [ ] **步骤 3：记录脱敏证据**

报告 HTTP 成功、返回的外部数据 ID、测试标识和执行时间；不报告请求头或 API Key。若响应不确定或网络中断，不再次发送，先让用户在简道云按测试标识核查。

- [ ] **步骤 4：交付检查结果**

列出修改文件、测试命令及结果、真实联调结果、范围外事项和 `git diff --stat`。不执行 `git commit`、`git push` 或创建 PR。
