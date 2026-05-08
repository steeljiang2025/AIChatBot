import { http } from "./http";
import type {
  MessageListApiResponse,
  SessionApiItem,
  SessionCreateBody,
  SessionListApiResponse,
  SessionPatchBody,
} from "./contracts";
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

/** POST /sessions — 创建空会话 */
export async function createSessionRemote(
  body: SessionCreateBody = {},
): Promise<ChatSession> {
  const { data } = await http.post<SessionApiItem>("/sessions", body);
  return mapSessionApiToChatSession(data);
}

/** PATCH /sessions/{id} */
export async function patchSessionRemote(
  sessionId: string,
  body: SessionPatchBody,
): Promise<ChatSession> {
  const { data } = await http.patch<SessionApiItem>(`/sessions/${sessionId}`, body);
  return mapSessionApiToChatSession(data);
}

/** DELETE /sessions/{id} */
export async function deleteSessionRemote(sessionId: string): Promise<void> {
  await http.delete(`/sessions/${sessionId}`);
}

/** GET /sessions/{id}/messages */
export async function fetchSessionMessages(
  sessionId: string,
  params?: { limit?: number; offset?: number },
): Promise<MessageListApiResponse> {
  const { data } = await http.get<MessageListApiResponse>(
    `/sessions/${sessionId}/messages`,
    {
      params: {
        limit: params?.limit ?? 200,
        offset: params?.offset ?? 0,
      },
    },
  );
  return data;
}
