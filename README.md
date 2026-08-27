# 涉案卷烟智能统计系统

这是一个面向单位内网、约 50 名工作人员使用的轻量扫码统计系统。

当前已经完成：

- FastAPI 和 Vue 工程骨架；
- Docker MySQL 与 Nginx 开发环境；
- MySQL 命名卷持久化；
- 登录、退出和当前用户；
- 管理员注册操作员；
- 田大、谢八、潘集、寿县和凤台五个分局。
- 卷烟品规新增、查询、编辑、停用和 Excel 导入；
- 扫描批次新建、列表、详情和空扫码工作区；
- 批次按角色与所属分局隔离，数据保存到 MySQL。

下一阶段是扫码识别、数量累计和未知/歧义编码处理。批次数量核对、Excel 导出和罚没烟登记快照尚未开发。

## 目录

```text
backend/       FastAPI 后端和后端测试
frontend/      Vue 前端和前端测试
deploy/        Nginx 与部署配置
docs/product/  技术方案、PRD 和 SPEC
docs/plans/    总体实施计划
tests/e2e/     Playwright 端到端测试
references/    原始参考资料，不得删除
```

## 开发环境启动

首次使用时在仓库根目录准备环境配置：

```powershell
Copy-Item .env.example .env
```

启动 MySQL 和 Nginx：

```powershell
docker compose --env-file .env -f compose.dev.yaml up -d --wait
docker compose --env-file .env -f compose.dev.yaml ps
```

初始化缺失数据表：

```powershell
Set-Location backend
.\.venv\python.exe -m app.cli.init_db
Set-Location ..
```

项目不使用 Alembic。`init_db` 不会删除、重建或自动修改已有表。

启动后端：

```powershell
Set-Location C:\Users\彭鸿徽\Desktop\Demo\backend
.\.venv\python.exe -m uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

启动前端：

```powershell
Set-Location C:\Users\彭鸿徽\Desktop\Demo
npm.cmd --prefix frontend run dev -- --host 0.0.0.0
```

浏览器访问 <http://localhost:8080>。

## 管理员和人员注册

当前开发库已创建管理员 `phh_admin`，密码由用户单独保管，不写入仓库。

管理员登录后，在“人员注册”页面为每名工作人员创建独立账号并选择所属分局。新注册人员固定为操作员，同一分局支持多人同时登录。

需要使用命令行创建管理员时：

```powershell
Set-Location backend
$securePassword = Read-Host "请输入管理员密码" -AsSecureString
$plainPassword = [Net.NetworkCredential]::new('', $securePassword).Password
$plainPassword | .\.venv\python.exe -m app.cli.create_user --username admin --display-name 系统管理员 --role ADMIN --password-stdin
Remove-Variable plainPassword
Set-Location ..
```

## 重启和数据持久化

前后端使用热更新，通常保存代码后自动刷新。手动重启时在对应终端按 `Ctrl+C`，再执行启动命令。

重启基础容器：

```powershell
docker compose --env-file .env -f compose.dev.yaml restart mysql nginx
docker compose --env-file .env -f compose.dev.yaml ps
```

MySQL 数据保存在固定命名卷 `scanner_mysql_data`。普通 `restart` 或 `down` 不删除数据；不要执行 `docker compose down -v`。

## 验证

```powershell
backend\.venv\python.exe -m pytest backend\tests -q
backend\.venv\python.exe -m ruff check backend
npm.cmd --prefix frontend run test:unit -- --run
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run test:e2e
docker compose --env-file .env -f compose.dev.yaml config
docker volume inspect scanner_mysql_data
```

后端 API 和 MySQL 集成测试要求 Docker MySQL 正在运行，并使用 `.env` 中独立的 `scanner_test` 测试库。
