import axios from "axios";
/**
 * 全局 axios 实例：所有后端请求统一走 `/api/*`，dev 通过 vite proxy 转发。
 * Phase 3 起会在拦截器里追加 Authorization Bearer 与 401 跳登录逻辑。
 */
export const http = axios.create({
    baseURL: "/api",
    timeout: 15_000,
    headers: { "Content-Type": "application/json" },
});
http.interceptors.response.use((resp) => resp, (error) => {
    return Promise.reject(error);
});
