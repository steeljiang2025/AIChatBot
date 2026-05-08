import { http } from "./http";
import type { SessionListApiResponse } from "./contracts";
import { mapSessionApiToChatSession } from "./mappers";
import type { ChatSession } from "@/types/chat";

/** GET /sessions — 与后端 query limit/offset 一致 */
export async function fetchSessions(params?: {
  limit?: number;
  offset?: number;
}): Promise<{ items: ChatSession[]; total: number; limit: number; offset: number }> {
  const { data } = await http.get<SessionListApiResponse>("/sessions", {
    params: {
      limit: params?.limit ?? 20,
      offset: params?.offset ?? 0,
    },
  });
  return {
    items: data.items.map(mapSessionApiToChatSession),
    total: data.total,
    limit: data.limit,
    offset: data.offset,
  };
}
