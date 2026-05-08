import { useAuthStore } from "@/store/authStore";

/** mock 登录产生的 token 前缀，与 `api/auth.ts` mockLogin 对齐 */
export function isMockAuthToken(token: string | null | undefined): boolean {
  return Boolean(token?.startsWith("mock."));
}

/**
 * 是否走本地 Mock SSE（mocks/sseServer）。
 * - `VITE_USE_MOCK_SSE=true` 强制 mock
 * - `VITE_USE_MOCK_SSE=false` 强制真实
 * - 未设置时：mock token → mock；真实 JWT → 真实
 */
export function useMockSse(): boolean {
  const v = import.meta.env.VITE_USE_MOCK_SSE;
  if (v === "true") return true;
  if (v === "false") return false;
  return isMockAuthToken(useAuthStore.getState().token);
}

/**
 * 会话列表是否仅用本地 seed / 内存（不请求 GET /sessions）。
 * 规则与 `useMockSse` 相同，可用 `VITE_USE_MOCK_SESSIONS` 单独覆盖。
 */
export function useMockSessionList(): boolean {
  const v = import.meta.env.VITE_USE_MOCK_SESSIONS;
  if (v === "true") return true;
  if (v === "false") return false;
  return isMockAuthToken(useAuthStore.getState().token);
}
