# AIChatBot Backend

FastAPI + LangGraph + PostgreSQL(pgvector) 后端。

## 快速开始

```bash
# 1) 启动数据库（位于仓库根目录）
make up

# 2) 准备 Python 环境（推荐 uv 或 venv + pip）
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3) 启动服务
uvicorn app.main:app --reload --port 8000

# 4) 访问 Swagger
open http://localhost:8000/docs
```

## 目录约定

```
backend/
  app/
    api/         # FastAPI 路由
    core/        # 配置、安全、依赖注入、异常处理
    db/          # SQLAlchemy 异步 engine 与会话
    main.py      # 应用入口
  tests/         # pytest 单元/集成测试
  pyproject.toml
```
