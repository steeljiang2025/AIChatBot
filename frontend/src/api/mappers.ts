import type { AuthUser } from "@/store/authStore";
import type { ChatSession } from "@/types/chat";
import type { AuthUserResponse, SessionApiItem } from "./contracts";

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
