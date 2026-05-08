import type { ChatStreamRequestBody } from "./contracts";

export type { ChatStreamRequestBody };

/** 构造与后端一致的 SSE 请求体 */
export function buildChatStreamBody(
  sessionId: string,
  content: string,
): ChatStreamRequestBody {
  return { session_id: sessionId, content };
}
