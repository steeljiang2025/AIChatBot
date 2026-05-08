import axios, { AxiosError, type AxiosInstance } from "axios";
import { useAuthStore } from "@/store/authStore";

/**
 * 全局 axios 实例：所有后端请求统一走 `/api/*`，dev 通过 vite proxy 转发。
 * 请求拦截器追加 `Authorization: Bearer <access_token>`（与 FastAPI JWT 中间件一致）。
 * 响应 401：清空本地会话并跳转登录（Phase 4）。
 */
export const http: AxiosInstance = axios.create({
  baseURL: "/api",
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

http.interceptors.request.use((config) => {
  const path = String(config.url ?? "");
  if (path.includes("/auth/login") || path.includes("/auth/refresh")) {
    delete config.headers.Authorization;
    return config;
  }
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().clear();
      const path = window.location.pathname;
      if (!path.startsWith("/login")) {
        window.location.assign("/login?reason=401");
      }
    }
    return Promise.reject(error);
  },
);
