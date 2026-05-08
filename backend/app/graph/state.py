"""STE-23：LangGraph AgentState（占位）。

设计要点（plan §3.7.1 (5) 已 probe 验证）：
- `messages`：`Annotated[list[AnyMessage], add_messages]` —— 历史累加
- `retries`：`Annotated[int, add]` —— 累加，多分支并发不丢
- 业务字段 `tenant_id` / `user_query` / `retrieved_schema` / `candidate_sql`
  / `validated_sql` / `rows` / `chart_spec` / `error` —— 默认覆盖语义

节点回写规则（避免前端重复展示）：
- 中间产出（generate_sql / chart）→ 写到业务字段，**不要**回 messages
- 最终回答（summarize）→ 写 messages，由 add_messages reducer 拼到历史
- error 字段每次进入 sql_validate 重置，进入失败时回写
- retries 由 sql_validate 失败时返回 `{"retries": 1}` 由 reducer 累加
"""

from __future__ import annotations

import uuid
from operator import add
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """工作流状态。所有字段都是可选（total=False），节点按需回写。

    必填字段（由调用方在 invoke 时传入）：
    - messages: 历史消息（langchain BaseMessage 子类列表）
    - tenant_id: UUID，用于 SQL 安全 / RAG 检索 / sql_exec bindparam(:tid)
    - user_query: 当前用户问句

    节点产出字段：
    - retrieved_schema: STE-21 hybrid_search 的 hits（结构化 dict 列表）
    - candidate_sql: sql_gen 节点产出
    - validated_sql: sql_validate 通过后的最终 SQL（含 :tid 占位符）
    - rows: sql_exec 执行结果（dict 列表）
    - chart_spec: chart 节点产出的 ECharts option dict 或 None
    - error: 任一阶段的错误描述；sql_validate 失败时由路由触发重试
    - retries: 累加重试次数；达到上限走失败分支
    """

    messages: Annotated[list[AnyMessage], add_messages]
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    user_query: str
    retrieved_schema: list[dict[str, Any]]
    candidate_sql: str
    validated_sql: str
    rows: list[dict[str, Any]]
    chart_spec: dict[str, Any] | None
    retries: Annotated[int, add]
    error: str | None


__all__ = ["AgentState"]
