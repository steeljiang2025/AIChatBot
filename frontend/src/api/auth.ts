// Phase 2 仅 mock；Phase 4 联调时改为真实 POST /auth/login
import { v4 as uuid } from "uuid";
import type { AuthUser } from "@/store/authStore";

export interface LoginInput {
  username: string;
  password: string;
}

export interface LoginResult {
  token: string;
  user: AuthUser;
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
      });
    }, FAKE_DELAY);
  });
}
