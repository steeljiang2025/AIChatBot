import type { AuthUser } from "@/store/authStore";
import type { ChatMessage, ChatSession, ChartSpec, Role, RowRecord, RowsPayload } from "@/types/chat";
import type { AuthUserResponse, MessageApiItem, SessionApiItem } from "./contracts";

/** GET /auth/me → 前端 AuthStore 用的 AuthUser */
export function mapAuthUserResponse(u: AuthUserResponse): AuthUser {
  return {
    id: u.id,
    username: u.email,
    displayName: u.display_name?.trim() ? u.display_name : u.email,
    tenantId: u.tenant_id,
    roles: u.roles ?? [],
  };
}

/** GET /sessions 单项 → 左栏 ChatSession */
export function mapSessionApiToChatSession(s: SessionApiItem): ChatSession {
  return {
    id: s.id,
    title: s.title?.trim() ? s.title : "新对话",
    updatedAt: s.updated_at,
  };
}

function coerceRole(r: string): Role {
  if (r === "user" || r === "assistant" || r === "system") return r;
  return "assistant";
}

/** GET /sessions/{id}/messages 单项 → ChatMessage（extra 中 sql / rows_preview / chart） */
export function mapMessageApiToChatMessage(m: MessageApiItem): ChatMessage {
  const extra = m.extra ?? {};
  const sql = typeof extra.sql === "string" ? extra.sql : undefined;
  const chart = (extra.chart ?? undefined) as ChartSpec | undefined;
  const errRaw = extra.error;
  const error =
    errRaw !== undefined && errRaw !== null
      ? { code: "BACKEND", message: String(errRaw) }
      : undefined;

  let rows: RowsPayload | undefined;
  const preview = extra.rows_preview;
  if (Array.isArray(preview) && preview.length > 0) {
    const first = preview[0];
    if (first && typeof first === "object" && !Array.isArray(first)) {
      const columns = Object.keys(first as object);
      rows = { columns, data: preview as RowRecord[] };
    }
  }

  return {
    id: m.id,
    sessionId: m.session_id,
    role: coerceRole(m.role),
    content: m.content,
    createdAt: m.created_at,
    sql,
    rows,
    chart,
    error,
  };
}
