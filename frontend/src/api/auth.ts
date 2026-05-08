// =============================================================
// 鉴权 API
// - VITE_USE_MOCK_AUTH !== "false"：Phase 2 本地 mock（admin/admin）
// - 否则：真实 POST /auth/login + GET /auth/me（字段与后端 Pydantic 一致）
// =============================================================

import { v4 as uuid } from "uuid";
import { http } from "./http";
import type { AuthLoginRequest, AuthTokenPair, AuthUserResponse } from "./contracts";
import { mapAuthUserResponse } from "./mappers";
import { useAuthStore, type AuthUser } from "@/store/authStore";

export interface LoginInput {
  username: string;
  password: string;
}

export interface LoginResult {
  token: string;
  user: AuthUser;
  refreshToken?: string | null;
}

const FAKE_DELAY = 500;

const PRESET_ACCOUNTS: Record<string, { password: string; user: AuthUser }> = {
  admin: {
    password: "admin",
    user: {
      id: "u-admin",
      username: "admin",
      displayName: "默认管理员",
      tenantId: "tenant-default",
      roles: ["admin"],
    },
  },
  demo: {
    password: "demo",
    user: {
      id: "u-demo",
      username: "demo",
      displayName: "演示账号",
      tenantId: "tenant-demo",
      roles: ["analyst"],
    },
  },
};

export function useMockAuth(): boolean {
  return import.meta.env.VITE_USE_MOCK_AUTH !== "false";
}

export function mockLogin(input: LoginInput): Promise<LoginResult> {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      const account = PRESET_ACCOUNTS[input.username];
      if (!account || account.password !== input.password) {
        reject(new Error("用户名或密码错误（提示：admin/admin、demo/demo）"));
        return;
      }
      resolve({
        token: `mock.${uuid()}.${Date.now().toString(36)}`,
        user: account.user,
        refreshToken: null,
      });
    }, FAKE_DELAY);
  });
}

/** POST /auth/login — 请求体与后端 `LoginRequest` 一致 */
export async function postAuthLogin(body: AuthLoginRequest): Promise<AuthTokenPair> {
  const { data } = await http.post<AuthTokenPair>("/auth/login", body);
  return data;
}

/** GET /auth/me — 需已带 Bearer access_token */
export async function getAuthMe(): Promise<AuthUserResponse> {
  const { data } = await http.get<AuthUserResponse>("/auth/me");
  return data;
}

/**
 * 真实登录：先换 token，再拉用户信息（第二次请求走拦截器自动带 Authorization）。
 */
export async function loginWithBackend(credentials: AuthLoginRequest): Promise<LoginResult> {
  const pair = await postAuthLogin(credentials);
  useAuthStore.setState({
    token: pair.access_token,
    refreshToken: pair.refresh_token,
  });
  const me = await getAuthMe();
  return {
    token: pair.access_token,
    user: mapAuthUserResponse(me),
    refreshToken: pair.refresh_token,
  };
}
