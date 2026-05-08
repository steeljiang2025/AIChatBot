// =============================================================
// useChatStream
//
// VITE_USE_MOCK_SSE !== "false"：走 mocks/sseServer。
// 否则：fetchEventSource("/api/chat/stream", ...) 与后端 STE-24 对齐：
//   - POST body: { session_id, content }
//   - Header: Authorization: Bearer <access_token>
//   - SSE data 字段与 `app/services/sse.py` 一致
// =============================================================

import { useCallback } from "react";
import {
  fetchEventSource,
  type EventSourceMessage,
} from "@microsoft/fetch-event-source";
import {
  startMockStream,
  type MockStreamHandle,
} from "@/mocks/sseServer";
import { buildChatStreamBody } from "@/api/chat";
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

const USE_MOCK = import.meta.env.VITE_USE_MOCK_SSE !== "false";

interface SendOptions {
  /** 远程 SSE endpoint（mock 关闭时使用） */
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
      const sql = (data.sql ?? "") as string;
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

      if (USE_MOCK) {
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

      fetchEventSource(endpoint, {
        method: "POST",
        headers,
        body: JSON.stringify(buildChatStreamBody(sessionId, prompt)),
        signal: abortController.signal,
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
          c.setError(
            sessionId,
            "STREAM_ERROR",
            err instanceof Error ? err.message : "网络错误",
          );
          c.finalizeAssistantMessage(sessionId);
          throw err;
        },
        openWhenHidden: true,
      });
    },
    [],
  );

  const abort = useCallback((sessionId: string) => {
    useChatStore.getState().abortStreaming(sessionId);
  }, []);

  return { send, abort };
}
