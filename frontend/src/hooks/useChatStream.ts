// =============================================================
// useChatStream
//
// Mock / 真实分流见 `config/runtimeMode.ts`（`useMockSse`）。
// 真实流：`fetchEventSource` + `onopen` 校验 content-type / 401；
// POST body `{ session_id, content }`；Bearer JWT。
// =============================================================

import { useCallback } from "react";
import {
  EventStreamContentType,
  fetchEventSource,
  type EventSourceMessage,
} from "@microsoft/fetch-event-source";
import {
  startMockStream,
  type MockStreamHandle,
} from "@/mocks/sseServer";
import { buildChatStreamBody } from "@/api/chat";
import { patchSessionRemote } from "@/api/sessions";
import { useMockSse } from "@/config/runtimeMode";
import { useAuthStore } from "@/store/authStore";
import { useChatStore } from "@/store/chatStore";
import { useChartStore } from "@/store/chartStore";
import { useSessionStore } from "@/store/sessionStore";
import type {
  ChartSpec,
  NodeStatus,
  RowCell,
  RowRecord,
  RowsPayload,
  SseEnvelope,
} from "@/types/chat";
import { dedupeSemicolonSql } from "@/utils/sqlDedupe";

interface SendOptions {
  endpoint?: string;
}

/** 兼容旧 mock 的「列对齐数组行」→ 与后端一致的对象行 */
function normalizeRowsPayload(raw: unknown): RowsPayload {
  const d = raw as { columns?: string[]; data?: unknown };
  const columns = d.columns ?? [];
  const rawData = d.data;
  if (!Array.isArray(rawData) || rawData.length === 0) {
    return { columns, data: [] };
  }
  const first = rawData[0];
  if (first !== null && typeof first === "object" && !Array.isArray(first)) {
    return { columns, data: rawData as RowRecord[] };
  }
  if (Array.isArray(first)) {
    const rows = (rawData as RowCell[][]).map((row) => {
      const obj: RowRecord = {};
      columns.forEach((c, i) => {
        obj[c] = row[i] ?? null;
      });
      return obj;
    });
    return { columns, data: rows };
  }
  return { columns, data: [] };
}

async function assertSseResponseOk(response: Response): Promise<void> {
  if (response.status === 401) {
    throw new Error("SSE_AUTH_401");
  }
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    throw new Error(`SSE_HTTP_${response.status}:${body.slice(0, 400)}`);
  }
  const ct = response.headers.get("content-type") ?? "";
  if (!ct.toLowerCase().includes(EventStreamContentType)) {
    throw new Error(`SSE_BAD_CONTENT_TYPE:${ct}`);
  }
}

function dispatch(sessionId: string, env: SseEnvelope): void {
  const chat = useChatStore.getState();
  const chart = useChartStore.getState();
  const data = env.data as Record<string, unknown>;
  switch (env.event) {
    case "token": {
      const delta = (data?.delta ?? "") as string;
      if (delta) chat.appendToken(sessionId, delta);
      break;
    }
    case "node": {
      const name = String(data.name ?? "");
      const status = data.status as NodeStatus;
      const detail = data.detail as string | undefined;
      if (name) chat.setNodeStatus(sessionId, name, status, detail);
      break;
    }
    case "sql": {
      const sql = dedupeSemicolonSql((data.sql ?? "") as string);
      chat.setSql(sessionId, sql);
      chart.setSql(sql);
      break;
    }
    case "rows": {
      const rows = normalizeRowsPayload(data);
      chat.setRows(sessionId, rows);
      chart.setRows(rows);
      break;
    }
    case "chart": {
      const option = (data.option ?? data) as ChartSpec;
      chat.setChart(sessionId, option);
      chart.setChart(option);
      break;
    }
    case "error": {
      const code = (data.code ?? "ERR") as string;
      const message = (data.message ?? "未知错误") as string;
      chat.setError(sessionId, code, message);
      break;
    }
    case "done": {
      chat.finalizeAssistantMessage(sessionId);
      break;
    }
  }
}

export function useChatStream(): {
  send: (sessionId: string, prompt: string, opts?: SendOptions) => void;
  abort: (sessionId: string) => void;
} {
  const send = useCallback(
    (sessionId: string, prompt: string, opts: SendOptions = {}) => {
      const chat = useChatStore.getState();
      const session = useSessionStore.getState();
      const chart = useChartStore.getState();

      chart.reset();
      chat.appendUserMessage(sessionId, prompt);

      const target = session.sessions.find((s) => s.id === sessionId);
      if (target && (target.title === "新对话" || target.title === "")) {
        const title = prompt.slice(0, 18) + (prompt.length > 18 ? "…" : "");
        session.renameSession(sessionId, title);
        if (!useMockSse()) {
          void patchSessionRemote(sessionId, { title }).catch(() => {
            /* 标题同步失败不阻塞对话 */
          });
        }
      }
      session.touch(sessionId);

      let mockHandle: MockStreamHandle | null = null;
      let abortController: AbortController | null = null;

      const handle = {
        abort: () => {
          mockHandle?.abort();
          abortController?.abort();
        },
      };

      chat.startAssistantMessage(sessionId, handle);

      if (useMockSse()) {
        mockHandle = startMockStream(prompt, {
          onEvent: (env) => dispatch(sessionId, env),
        });
        return;
      }

      abortController = new AbortController();
      const endpoint = opts.endpoint ?? "/api/chat/stream";
      const token = useAuthStore.getState().token;
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }

      void fetchEventSource(endpoint, {
        method: "POST",
        headers,
        body: JSON.stringify(buildChatStreamBody(sessionId, prompt)),
        signal: abortController.signal,
        async onopen(response) {
          await assertSseResponseOk(response);
        },
        onmessage(ev: EventSourceMessage) {
          if (!ev.event) return;
          try {
            const data = ev.data ? JSON.parse(ev.data) : {};
            dispatch(sessionId, {
              event: ev.event as SseEnvelope["event"],
              data,
            });
          } catch {
            // ignore malformed payloads
          }
        },
        onerror(err: unknown) {
          const c = useChatStore.getState();
          const msg = err instanceof Error ? err.message : String(err);
          if (msg === "SSE_AUTH_401") {
            useAuthStore.getState().clear();
            window.location.assign("/login?reason=401");
            throw err instanceof Error ? err : new Error(msg);
          }
          c.setError(
            sessionId,
            "STREAM_ERROR",
            msg || "网络错误",
          );
          c.finalizeAssistantMessage(sessionId);
          throw err instanceof Error ? err : new Error(msg);
        },
        openWhenHidden: true,
      }).catch(() => {
        /* onerror 已 throw 时进入；静默避免控制台 Unhandled */
      });
    },
    [],
  );

  const abort = useCallback((sessionId: string) => {
    useChatStore.getState().abortStreaming(sessionId);
  }, []);

  return { send, abort };
}
