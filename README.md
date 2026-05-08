# AIChatBot · 智能数据分析助理

基于 **FastAPI + LangGraph + React + PostgreSQL(pgvector)** 的多租户自然语言数据分析系统。
用户用日常中文提问，系统通过 RAG 检索语义元数据、生成并安全校验 SQL、查询数据库后实时回流可视化图表。

> 详细规划见 [`.cursor/plans/智能数据分析系统模块规划_34b277f9.plan.md`](.cursor/plans/智能数据分析系统模块规划_34b277f9.plan.md)
> 项目管理在 Linear：[智能数据分析助理](https://linear.app/steeljiang/project/智能数据分析助理-f489d5fbb142)

## 架构

```
React 18 + AntD + ECharts        FastAPI + LangGraph
       ↑                                ↑
       └──────── /api/* (SSE) ──────────┘
                       │
              PostgreSQL 16 + pgvector
              (meta / rag / biz / checkpoint)
                       │
              Qwen3 Chat / text-embedding-v4
              (阿里云百炼 OpenAI 兼容端点)
```

## 仓库结构

```
AIChatBot/
├── backend/             # FastAPI 后端（容器化）
│   ├── app/
│   │   ├── api/         # 路由（health / auth / sessions / semantics / chat）
│   │   ├── core/        # 配置、日志、安全（Phase3 起完整）
│   │   ├── db/          # SQLAlchemy 异步 engine
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   ├── .dockerignore
│   └── pyproject.toml
├── frontend/            # Vite + React + TS（容器化）
│   ├── src/
│   ├── Dockerfile
│   ├── .dockerignore
│   └── package.json
├── infra/
│   ├── podman-compose.yml      # 全栈 compose（postgres + backend + frontend）
│   ├── .env.example            # 编排层（postgres + 端口 + 共享密钥）
│   └── postgres/
│       ├── init.sql            # extensions + schema 初始化
│       └── init-roles.sh       # 应用账号 / 业务库只读账号
├── scripts/
│   └── smoke.sh         # Phase1 端到端冒烟检查（容器视角）
├── .gitignore
├── Makefile
└── README.md
```

> **三处独立 `.env`**（前后端是两个独立项目，配置分开维护）：
> - `infra/.env`：postgres 账号/密码/库 + 共享数据库密钥 + 宿主机端口映射；用于 podman-compose 占位符插值与 postgres 容器初始化
> - `backend/.env`：APP/CORS/JWT/Qwen 等后端运行时配置；通过 compose 的 `env_file` 注入 backend 容器，本地直跑时由 `pydantic-settings` 加载
> - `frontend/.env`：`VITE_PROXY_TARGET`、HMR 轮询开关；通过 compose 的 `env_file` 注入 frontend 容器
> - 三个 `.env` 都不进 git，对应的 `.env.example` 进版本控

## 快速开始（Phase 1，全栈容器化）

> 本项目所有服务（postgres / backend / frontend）都通过 **Podman + podman-compose** 跑在容器里，**禁止**直接用宿主机 Python venv 或 pnpm 启动后端/前端。开发态通过 volume 挂载源码 + uvicorn `--reload` / Vite HMR 获得热更新。

### 1. 准备环境变量

```bash
cp infra/.env.example     infra/.env       # postgres 账号/密码/库、共享密钥、宿主机端口
cp backend/.env.example   backend/.env     # 后端：APP/CORS/JWT/Qwen
cp frontend/.env.example  frontend/.env    # 前端：VITE_PROXY_TARGET / HMR 轮询
# 按需修改 POSTGRES_PASSWORD、APP_DB_PASSWORD、BIZ_RO_PASSWORD、DASHSCOPE_API_KEY、JWT_SECRET 等
```

数据库连接串（`META_DB_URL` / `BIZ_DB_URL`）由 compose 在 `backend.environment` 中用 `infra/.env` 的密码插值生成，无需在 `backend/.env` 中重复维护。如果要从宿主机直连数据库（非容器跑），可在 `backend/.env` 中追加并把 host 改成 `localhost`。

### 2. 一条命令起全栈

```bash
make up
```

该命令会：

1. 构建 `aichatbot-backend:dev` / `aichatbot-frontend:dev` 镜像（首次较慢）。
2. 拉起 `aichatbot-postgres`（pgvector）容器，自动执行 `init.sql` 和 `init-roles.sh`。
3. 拉起 `aichatbot-backend` 容器（uvicorn `--reload`，挂载 `backend/app`、`backend/tests`）。
4. 拉起 `aichatbot-frontend` 容器（Vite dev server，挂载 `frontend/src` 等）。

入口（端口由 `infra/.env` 中的 `BACKEND_PORT` / `FRONTEND_PORT` 决定，默认 8001 / 5174）：

- 前端：<http://localhost:5174/health>（看到健康徽标显示后端 · OK / meta DB · OK / biz DB · OK）
- 后端 Swagger：<http://localhost:8001/docs>
- 后端健康：<http://localhost:8001/health>

### 3. 常用容器化命令

```bash
make ps           # 查看容器状态
make logs         # 跟踪三套服务日志
make psql         # 进入 postgres 容器 psql
make be-shell     # 进入 backend 容器 bash
make fe-shell     # 进入 frontend 容器 sh
make be-test      # 容器内跑后端 pytest
make fe-test      # 容器内跑前端 vitest
make fe-build     # 容器内构建前端产物
make rebuild      # 仅重建 backend / frontend 镜像
make down         # 停掉全部容器（数据卷保留）
```

### 4. 端到端冒烟测试

```bash
make smoke                              # 容器健康 + /health + 5173 + schema/角色
bash scripts/smoke.sh --with-tests      # 顺带跑容器内 pytest + vitest
```

## Phase 4（前后端联调）— 已实现

目标：去掉 Phase 2 的纯前端 Mock，在 **真实 JWT + REST + SSE** 下跑通工作区。

### 前端行为摘要

| 能力 | 说明 |
|------|------|
| 会话 | `GET/POST/PATCH/DELETE /sessions`；切换会话时 `GET .../messages` 拉历史 |
| 聊天流 | `POST /chat/stream` + `fetchEventSource`；`onopen` 校验 401 / content-type |
| Mock 分流 | `token` 以 `mock.` 开头 → 本地 seed + mock SSE（无后端也可演示）；真实 JWT → 走后端 |
| 环境变量 | `VITE_USE_MOCK_SSE` / `VITE_USE_MOCK_SESSIONS` / `VITE_USE_MOCK_AUTH` 可显式 `true`/`false` 覆盖 |
| 401 | axios 与 SSE 均会清空登录态并跳转 `/login?reason=401` |

### 全栈启动（与 Phase 1 一致）

```bash
cp infra/.env.example infra/.env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# 填 DASHSCOPE_API_KEY、JWT_SECRET；联调真实后端时把 frontend/.env 中 VITE_USE_MOCK_* 设为 false
make up
```

浏览器：`http://localhost:<FRONTEND_PORT>/`（默认见 `infra/.env` 中 `FRONTEND_PORT`，常见为 5174）→ 使用 **真实租户** 登录（`VITE_USE_MOCK_AUTH=false`）→ Workspace 自动拉会话与历史消息 → 提问走 SSE。

### 后端可观测性

- 每个 HTTP 响应带 **`X-Request-ID`**（`RequestIdMiddleware`），便于与日志关联。

### 验收清单（Phase 4.3 / 4.5）

- [ ] 登录 → 新建会话 → 自然语言提问 → 出现 SQL / 表格 / 图表（依赖 Qwen 与业务库数据）
- [ ] 同一会话多轮追问（LangGraph PostgresSaver 线程 id = `session_id`）
- [ ] SQL 校验失败或权限错误时 SSE `error` + 页面兜底
- [ ] `podman compose ps` 全绿、`make smoke` 通过

---

## 历史阶段（已完成）

- **Phase 2**：前端三栏 Workspace、登录页、聊天 UI、ECharts、SSE Mock（Mock 驱动）
- **Phase 3**：JWT 鉴权、Alembic 迁移、Qwen3 接入、语义 RAG、SQL 安全层、LangGraph + AsyncPostgresSaver、`/chat/stream` SSE

## 开发规则

- 用日常中文短语驱动开发流程，详见 [`.cursor/rules/dev-flow.mdc`](.cursor/rules/dev-flow.mdc)
- 例如：「**开始做基础设施**」、「**看下我的活**」、「**STE-5 做完了**」

## License

MIT
