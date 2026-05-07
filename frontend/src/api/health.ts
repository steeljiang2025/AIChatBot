import { http } from "./http";

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  env: string;
  db: { meta: "ok" | "down"; biz: "ok" | "down" };
}

export async function fetchHealth(): Promise<HealthResponse> {
  const resp = await http.get<HealthResponse>("/health");
  return resp.data;
}
