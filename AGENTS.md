# 涉案卷烟智能统计系统开发约定

## 1. 开始前必须阅读

1. `docs/product/01-涉案卷烟智能统计系统-技术方案.md`
2. `docs/product/02-涉案卷烟智能统计系统-PRD.md`
3. `docs/product/03-涉案卷烟智能统计系统-SPEC.md`
4. `docs/plans/00-系统分阶段实施计划.md`
5. 当前阶段经用户批准的设计或实施说明

冲突优先级：用户最新明确指令 > SPEC > PRD > 技术方案 > 实施计划。发现冲突先说明，不自行扩大范围。

## 2. 技术和规模

- 约 50 名内网用户，采用简单单体应用；
- 前端：Vue 3、TypeScript、Vite、Element Plus；
- 后端：Python 3.12、FastAPI、Pydantic、SQLAlchemy 2.x；
- 数据库：MySQL 8.x、InnoDB、`utf8mb4`；
- 网关：Nginx；
- 部署：Windows Docker Desktop，最终使用 Docker Compose；
- 测试：pytest、Ruff、Vitest、ESLint、Playwright。

不引入 Redis、消息队列、微服务、Kubernetes 或数据库迁移框架，除非用户以后明确批准。

## 3. 目录职责

```text
backend/       FastAPI、业务服务、SQLAlchemy 模型和后端测试
frontend/      Vue 页面、状态、API 客户端和前端测试
deploy/        Nginx 和部署配置
docs/product/  技术方案、PRD 和 SPEC
docs/plans/    总体分阶段实施计划
tests/e2e/     浏览器端到端测试
references/    用户提供的原始参考资料
```

API 控制器不直接承载复杂业务规则；业务规则放服务层。Vue 组件不直接维护权威业务数据，最终结果以后端返回为准。

## 4. 分阶段开发

- 一次只执行一个已经批准的阶段，不提前开发后续模块；
- 每个模块按“契约 → 失败测试 → 数据库 → 后端 → 前端 → 联调 → 回归验证”完成闭环；
- 开始前列出对应 PRD/SPEC、预计修改文件、验证命令和范围外事项；
- 完成后列出实际修改、测试证据、字段对照、剩余事项和 Git diff；
- 未经用户要求，不执行 `git commit`、`git push`、创建 PR 或修改远程仓库。

## 5. 测试命令

```powershell
backend\.venv\Scripts\pytest.exe backend\tests -q
backend\.venv\Scripts\ruff.exe check backend
npm.cmd --prefix frontend run test:unit -- --run
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
docker compose --env-file .env -f compose.dev.yaml config
```

功能或 Bug 修复先写能正确失败的测试，再写最小实现。纯文档和删除无运行影响的死代码不制造无意义测试，但必须执行现有回归测试和静态检查。

## 6. 数据库规则

- 不使用 Alembic；
- `init_db` 只创建缺失表并校验必要结构，不删除、重建或修改已有表；
- 应用启动不得自动执行 DDL；
- 已有表需要调整时，先备份、列出明确 SQL，并取得用户逐次确认；
- 生产实现只使用 MySQL，数据库相关测试使用独立 MySQL 测试库；
- 条码、包码、案件编号和批次编号使用字符串；金额使用 `DECIMAL`；
- 数据库时间保存 UTC，前端按中国标准时间显示；
- 包码不设全局唯一约束；
- `scan_events` 只追加；
- 扫码使用事务、行锁和唯一 `request_id` 保证幂等；
- 历史批次保存品规快照；
- MySQL 使用命名卷 `scanner_mysql_data`，禁止对业务数据执行 `docker compose down -v`。

## 7. API 和前端规则

- API 统一使用 `/api/v1`；
- 写接口必须鉴权、校验权限并返回 `trace_id`；
- 错误响应使用 SPEC 错误码，不暴露内部堆栈；
- OpenAPI、Pydantic 模型、TypeScript 类型和实际响应字段保持一致；
- 扫码页默认聚焦，回车提交，完成后清空并恢复焦点；
- 成功、未知、歧义和失败必须有文字提示；
- 不在 `localStorage` 保存正式业务数据或登录密钥；
- 罚没烟功能本期只生成快照，不实现真实推送、模拟推送或自动重试。

## 8. 安全和文件保护

- 不提交 `.env`、密码、Token、真实接口地址、数据库数据、备份、导出和日志；
- 仓库只保留无真实秘密的 `.env.example`；
- 日志不记录密码、Cookie、Token 或完整外部鉴权信息；
- 保留并忽略 `.codex/`；
- 不删除或覆盖 `references/` 中用户提供的 `.doc`、`.xlsx`、`.html`、`.py` 文件；
- 不使用 `git reset --hard`、`git checkout --` 等破坏性命令。

## 9. 完成定义

只有当前阶段范围全部实现、适用测试和构建通过、字段契约一致、MySQL 持久化已验证、没有真实秘密或未解释改动，并已向用户提供证据时，才能称为完成。
