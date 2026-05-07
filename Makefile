.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE_FILE := infra/podman-compose.yml
# 编排层 .env（postgres + 端口 + 共享密钥），用于 podman-compose 的 ${...} 插值
# 后端、前端各自的 .env 由 compose 文件中的 env_file 指令注入对应容器
ENV_FILE     := infra/.env

# 优先使用 podman-compose；若用户机器只有 podman 4.x，可用 `podman compose`
ifeq (, $(shell command -v podman-compose 2>/dev/null))
	COMPOSE := podman compose
else
	COMPOSE := podman-compose
endif

# 全部命令都走容器，禁止依赖宿主机 venv / pnpm
.PHONY: help up up-build down restart logs ps psql \
        be-shell be-test be-fmt be-lint \
        fe-shell fe-test fe-build fe-lint fe-fmt \
        rebuild fmt lint smoke

help: ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS=":.*?## "} {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---------- 全栈生命周期 ----------
up: ## 启动全栈（postgres + backend + frontend），首次会自动构建镜像
	$(COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d

up-build: ## 强制重建镜像后启动
	$(COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) up -d --build

down: ## 关停全部容器（保留数据卷）
	$(COMPOSE) -f $(COMPOSE_FILE) down

restart: ## 重启 backend / frontend（保留 postgres）
	podman restart aichatbot-backend aichatbot-frontend

rebuild: ## 仅重建 backend + frontend 镜像
	$(COMPOSE) --env-file $(ENV_FILE) -f $(COMPOSE_FILE) build backend frontend

logs: ## 跟踪所有服务日志
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=100

ps: ## 查看容器状态
	podman ps --filter "label=io.podman.compose.project=infra"

# ---------- 数据库 ----------
psql: ## 进入容器 psql shell
	podman exec -it aichatbot-postgres psql -U postgres -d aichatbot

# ---------- Backend（容器内执行） ----------
be-shell: ## 进入 backend 容器 bash
	podman exec -it aichatbot-backend bash

be-test: ## 容器内运行后端测试
	podman exec aichatbot-backend pytest -v

be-fmt: ## 容器内格式化后端代码
	podman exec aichatbot-backend ruff format .

be-lint: ## 容器内静态检查
	podman exec aichatbot-backend ruff check .

# ---------- Frontend（容器内执行） ----------
fe-shell: ## 进入 frontend 容器 sh
	podman exec -it aichatbot-frontend sh

fe-test: ## 容器内运行前端单测
	podman exec aichatbot-frontend pnpm test --run

fe-build: ## 容器内构建前端产物
	podman exec aichatbot-frontend pnpm build

fe-lint: ## 容器内 ESLint
	podman exec aichatbot-frontend pnpm lint

fe-fmt: ## 容器内 Prettier
	podman exec aichatbot-frontend pnpm prettier --write "src/**/*.{ts,tsx,css}"

# ---------- 聚合命令 ----------
fmt: be-fmt fe-fmt ## 全栈格式化
lint: be-lint fe-lint ## 全栈静态检查

smoke: ## Phase1 端到端冒烟测试（容器化）
	@bash scripts/smoke.sh
