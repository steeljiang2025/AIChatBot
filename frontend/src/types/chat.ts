// =============================================================
// 聊天 / 会话 / 流式事件领域模型
//
// SSE 与后端 `app/services/sse.py` + `chat_service` 对齐：
//   token  { delta, node, step?, model? }
//   node   { name, status }   // 后端目前固定 status: "ok"
//   sql    { sql }
//   rows   { columns, data }  // data 为对象数组（每行键与 columns 一致）
//   chart  { option }
//   error  { code, message }
//   done   { message_id, ok? }
// =============================================================

import type { EChartsOption } from "echarts";

export type Role = "user" | "assistant" | "system";

export interface ChatSession {
  id: string;
  title: string;
  /** ISO 时间，用于左栏「今天/昨天/更早」分组 */
  updatedAt: string;
}

export type NodeStatus = "pending" | "running" | "ok" | "error";

export interface ThinkingNode {
  /** 与后端 updates chunk 的 dict key 一致 */
  name: string;
  label: string;
  status: NodeStatus;
  detail?: string;
}

export type RowCell = string | number | boolean | null;

/** 一行记录：键为列名（与后端 SQL 行 dict 一致） */
export type RowRecord = Record<string, RowCell>;

export interface RowsPayload {
  columns: string[];
  /** 后端 `sse.translate_chunk` 推送为对象数组 */
  data: RowRecord[];
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

/** POST /chat/stream 的 token 事件 data（与后端一致） */
export interface SseTokenPayload {
  delta: string;
  node: string;
  step?: number;
  model?: string;
}

export interface SseNodePayload {
  name: string;
  status: string;
  detail?: string;
}

export interface SseSqlPayload {
  sql: string;
}

export interface SseRowsPayload {
  columns: string[];
  data: RowRecord[];
}

export interface SseChartPayload {
  option: ChartSpec;
}

export interface SseErrorPayload {
  code: string;
  message: string;
}

export interface SseDonePayload {
  message_id: string;
  ok?: boolean;
}

export interface SseEnvelope<T = unknown> {
  event: SseEventName;
  data: T;
}
