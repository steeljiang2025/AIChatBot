// =============================================================
// 聊天 / 会话 / 流式事件领域模型
// 与后端最终的 SSE 协议对齐（plan.md §5）：
//   token  { delta }
//   node   { name, status }
//   sql    { sql }
//   rows   { columns, data }
//   chart  { option }
//   error  { code, message }
//   done   { message_id }
// =============================================================

import type { EChartsOption } from "echarts";

export type Role = "user" | "assistant" | "system";

export interface ChatSession {
  id: string;
  title: string;
  /** ISO 时间，用于左栏「今天/昨天/更早」分组 */
  updatedAt: string;
}

export type NodeName =
  | "intent"
  | "retrieve"
  | "sql_gen"
  | "sql_validate"
  | "tenant_guard"
  | "sql_exec"
  | "chart"
  | "summarize";

export type NodeStatus = "pending" | "running" | "ok" | "error";

export interface ThinkingNode {
  name: NodeName;
  label: string;
  status: NodeStatus;
  detail?: string;
}

export interface RowsPayload {
  columns: string[];
  data: Array<Array<string | number | boolean | null>>;
}

export type ChartSpec = EChartsOption;

export interface ChatMessage {
  id: string;
  sessionId: string;
  role: Role;
  /** 流式叠加后的最终文本；Markdown 字符串 */
  content: string;
  createdAt: string;
  /** 是否仍在流式生成中 */
  streaming?: boolean;
  /** 助手轨迹：节点进度 */
  thinking?: ThinkingNode[];
  /** 校验后的最终 SQL */
  sql?: string;
  /** 查询结果 */
  rows?: RowsPayload;
  /** ECharts option（推荐图表） */
  chart?: ChartSpec;
  /** 错误信息 */
  error?: { code: string; message: string };
}

export type SseEventName =
  | "token"
  | "node"
  | "sql"
  | "rows"
  | "chart"
  | "error"
  | "done";

export interface SseEnvelope<T = unknown> {
  event: SseEventName;
  data: T;
}
