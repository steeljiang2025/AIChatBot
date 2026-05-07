import { create } from "zustand";
import { v4 as uuid } from "uuid";
import dayjs from "dayjs";
import type {
  ChatMessage,
  ChartSpec,
  NodeName,
  NodeStatus,
  RowsPayload,
  ThinkingNode,
} from "@/types/chat";

const NODE_LABEL: Record<NodeName, string> = {
  intent: "意图理解",
  retrieve: "语义检索",
  sql_gen: "SQL 生成",
  sql_validate: "SQL 安全校验",
  tenant_guard: "租户隔离注入",
  sql_exec: "查询执行",
  chart: "图表推荐",
  summarize: "总结回答",
};

interface StreamHandle {
  /** 用户主动停止当前流式生成 */
  abort: () => void;
}

interface ChatState {
  /** sessionId -> messages */
  messagesBySession: Record<string, ChatMessage[]>;
  /** sessionId -> 当前正在追加 token 的助手消息 id */
  streamingMessageId: Record<string, string | undefined>;
  /** sessionId -> 流句柄（abort） */
  streamingHandle: Record<string, StreamHandle | undefined>;

  getMessages: (sessionId: string) => ChatMessage[];
  appendUserMessage: (sessionId: string, content: string) => ChatMessage;
  startAssistantMessage: (
    sessionId: string,
    handle?: StreamHandle,
  ) => ChatMessage;
  appendToken: (sessionId: string, delta: string) => void;
  setNodeStatus: (
    sessionId: string,
    name: NodeName,
    status: NodeStatus,
    detail?: string,
  ) => void;
  setSql: (sessionId: string, sql: string) => void;
  setRows: (sessionId: string, rows: RowsPayload) => void;
  setChart: (sessionId: string, chart: ChartSpec) => void;
  setError: (sessionId: string, code: string, message: string) => void;
  finalizeAssistantMessage: (sessionId: string) => void;
  abortStreaming: (sessionId: string) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messagesBySession: {},
  streamingMessageId: {},
  streamingHandle: {},

  getMessages: (sessionId) => get().messagesBySession[sessionId] ?? [],

  appendUserMessage: (sessionId, content) => {
    const msg: ChatMessage = {
      id: uuid(),
      sessionId,
      role: "user",
      content,
      createdAt: dayjs().toISOString(),
    };
    set((s) => ({
      messagesBySession: {
        ...s.messagesBySession,
        [sessionId]: [...(s.messagesBySession[sessionId] ?? []), msg],
      },
    }));
    return msg;
  },

  startAssistantMessage: (sessionId, handle) => {
    const msg: ChatMessage = {
      id: uuid(),
      sessionId,
      role: "assistant",
      content: "",
      createdAt: dayjs().toISOString(),
      streaming: true,
      thinking: [],
    };
    set((s) => ({
      messagesBySession: {
        ...s.messagesBySession,
        [sessionId]: [...(s.messagesBySession[sessionId] ?? []), msg],
      },
      streamingMessageId: {
        ...s.streamingMessageId,
        [sessionId]: msg.id,
      },
      streamingHandle: { ...s.streamingHandle, [sessionId]: handle },
    }));
    return msg;
  },

  appendToken: (sessionId, delta) =>
    set((s) =>
      patchAssistant(s, sessionId, (m) => ({ content: m.content + delta })),
    ),

  setNodeStatus: (sessionId, name, status, detail) =>
    set((s) =>
      patchAssistant(s, sessionId, (m) => {
        const trace = m.thinking ?? [];
        const idx = trace.findIndex((n) => n.name === name);
        const node: ThinkingNode = {
          name,
          label: NODE_LABEL[name],
          status,
          detail,
        };
        const next = idx >= 0 ? [...trace] : [...trace, node];
        if (idx >= 0) next[idx] = { ...next[idx], ...node };
        return { thinking: next };
      }),
    ),

  setSql: (sessionId, sql) =>
    set((s) => patchAssistant(s, sessionId, () => ({ sql }))),

  setRows: (sessionId, rows) =>
    set((s) => patchAssistant(s, sessionId, () => ({ rows }))),

  setChart: (sessionId, chart) =>
    set((s) => patchAssistant(s, sessionId, () => ({ chart }))),

  setError: (sessionId, code, message) =>
    set((s) =>
      patchAssistant(s, sessionId, () => ({
        error: { code, message },
        streaming: false,
      })),
    ),

  finalizeAssistantMessage: (sessionId) =>
    set((s) => {
      const next = patchAssistant(s, sessionId, () => ({ streaming: false }));
      return {
        ...next,
        streamingMessageId: {
          ...s.streamingMessageId,
          [sessionId]: undefined,
        },
        streamingHandle: { ...s.streamingHandle, [sessionId]: undefined },
      };
    }),

  abortStreaming: (sessionId) => {
    const handle = get().streamingHandle[sessionId];
    handle?.abort();
    get().finalizeAssistantMessage(sessionId);
  },
}));

/** 给当前会话最后一条助手消息打补丁的内部 helper */
function patchAssistant(
  state: ChatState,
  sessionId: string,
  patch: (m: ChatMessage) => Partial<ChatMessage>,
): Pick<ChatState, "messagesBySession"> {
  const list = state.messagesBySession[sessionId];
  if (!list || list.length === 0) return { messagesBySession: state.messagesBySession };
  const targetId = state.streamingMessageId[sessionId];
  const next = list.map((m) =>
    (targetId ? m.id === targetId : false) ? { ...m, ...patch(m) } : m,
  );
  return {
    messagesBySession: { ...state.messagesBySession, [sessionId]: next },
  };
}
