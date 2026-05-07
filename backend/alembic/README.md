# Alembic — AIChatBot 数据库迁移

## 作用域

只管理 **`meta`** 与 **`rag`** 两个 schema 内的表 / 索引 / 约束。

明确**排除**的两个 schema：

| Schema       | 谁来管                                                                | 原因                                                            |
| ------------ | ------------------------------------------------------------------ | ------------------------------------------------------------- |
| `checkpoint` | `langgraph-checkpoint-postgres` 的 `AsyncPostgresSaver.setup()` 自治 | 4 张表（`checkpoints` / `checkpoint_writes` / `checkpoint_blobs` / `checkpoint_migrations`）由 langgraph 自身 schema 版本控制，**禁止人为 ALTER**（详见 plan.md §3.7.1） |
| `biz`        | 业务数据导入/抽取脚本                                                       | 业务库表由数仓/上游同步，alembic 只读语义层                                    |

排除逻辑实现在 `env.py` 的 `include_object` / `include_name` 钩子。

## 常用命令（容器内）

```bash
# 进入 backend 容器
podman exec -it aichatbot-backend bash

# 应用所有未执行迁移
alembic upgrade head

# 回滚一步
alembic downgrade -1

# 查看当前版本
alembic current

# 查看历史
alembic history --verbose

# 生成新迁移（autogenerate；之后必须人工 review，vector/tsvector 列不一定准）
alembic revision --autogenerate -m "add foo"
```

> 数据库 URL 由 `env.py` 按 `META_DB_URL`（容器） → `Settings.meta_db_url`（本地兜底）的优先级解析，不在 `alembic.ini` 中硬编码。

## 验证

```bash
# 表 + 索引落地检查
podman exec aichatbot-postgres psql -U app_user -d aichatbot \
  -c "\dt meta.*"  -c "\dt rag.*"  -c "\d+ rag.semantic_tables"

# 确认 alembic 没有动 checkpoint schema
podman exec aichatbot-postgres psql -U app_user -d aichatbot \
  -c "SELECT tablename FROM pg_tables WHERE schemaname='checkpoint';"
# 期望：空（除非 langgraph 已经跑过 setup()）
```
