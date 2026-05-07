// =============================================================
// useChatStream
//
// Phase 2 阶段：直接对接本地 mocks/sseServer 的事件流。
// Phase 4 联调时改为：fetchEventSource("/api/chat/stream", { ... })。
//
// 设计要点：
// - 不在 hook 中订阅会变化的 store 字段（避免每次状态变化都触发 ChatArea
//   重渲染），所有读写都通过 store.getState() 直接访问。
// - send/abort 用 useCallback 缓存，依赖项保持空数组。
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
import { useChatStore } from "@/store/chatStore";
import { useChartStore } from "@/store/chartStore";
import { useSessionStore } from "@/store/sessionStore";
import type {
  ChartSpec,
  NodeName,
  NodeStatus,
  RowsPayload,
  SseEnvelope,
} from "@/types/chat";

const USE_MOCK = import.meta.env.VITE_USE_MOCK_SSE !== "false";

interface SendOptions {
  /** 远程 SSE endpoint（mock 关闭时使用） */
  endpoint?: string;
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
      const name = data.name as NodeName;
      const status = data.status as NodeStatus;
      const detail = data.detail as string | undefined;
      chat.setNodeStatus(sessionId, name, status, detail);
      break;
    }
    case "sql": {
      const sql = (data.sql ?? "") as string;
      chat.setSql(sessionId, sql);
      chart.setSql(sql);
      break;
    }
    case "rows": {
      const rows = data as unknown as RowsPayload;
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
      fetchEventSource(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, prompt }),
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
