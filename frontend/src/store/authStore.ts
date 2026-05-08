import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AuthUser {
  id: string;
  username: string;
  displayName: string;
  tenantId: string;
  roles: string[];
}

interface AuthState {
  token: string | null;
  /** 与后端 refresh_token 对齐；mock 登录时为 null */
  refreshToken: string | null;
  user: AuthUser | null;
  setSession: (
    token: string,
    user: AuthUser,
    refreshToken?: string | null,
  ) => void;
  clear: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      setSession: (token, user, refreshToken = null) =>
        set({ token, user, refreshToken: refreshToken ?? null }),
      clear: () => set({ token: null, refreshToken: null, user: null }),
      isAuthenticated: () => Boolean(get().token),
    }),
    { name: "aichatbot.auth" },
  ),
);
