/**
 * 与 FastAPI 后端 JSON 字段对齐的契约（Pydantic 默认 snake_case）。
 * UI 层仍可使用 camelCase 的 ChatSession 等，通过 mapper 转换。
 */

/** POST /auth/login */
export interface AuthLoginRequest {
  tenant_code: string;
  email: string;
  password: string;
}

/** POST /auth/login 响应 */
export interface AuthTokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/** GET /auth/me 响应 */
export interface AuthUserResponse {
  id: string;
  tenant_id: string;
  email: string;
  display_name: string | null;
  roles: string[];
  is_active: boolean;
}

/** POST /sessions */
export interface SessionCreateBody {
  title?: string | null;
}

/** PATCH /sessions/{id} */
export interface SessionPatchBody {
  title?: string | null;
}

/** GET /sessions 单项 */
export interface SessionApiItem {
  id: string;
  tenant_id: string;
  user_id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

/** GET /sessions 列表 */
export interface SessionListApiResponse {
  items: SessionApiItem[];
  total: number;
  limit: number;
  offset: number;
}

/** GET /sessions/{id}/messages 单项 */
export interface MessageApiItem {
  id: string;
  session_id: string;
  tenant_id: string;
  user_id: string | null;
  role: string;
  content: string;
  token_usage: Record<string, unknown> | null;
  extra: Record<string, unknown> | null;
  created_at: string;
}

/** GET /sessions/{id}/messages 列表 */
export interface MessageListApiResponse {
  items: MessageApiItem[];
  total: number;
  limit: number;
  offset: number;
}

/** POST /chat/stream 请求体（与 backend ChatStreamRequest 一致） */
export interface ChatStreamRequestBody {
  session_id: string;
  content: string;
}
