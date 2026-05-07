import { create } from "zustand";
import { v4 as uuid } from "uuid";
import dayjs from "dayjs";
import type { ChatSession } from "@/types/chat";

interface SessionState {
  sessions: ChatSession[];
  activeId: string | null;
  hydrate: (sessions: ChatSession[]) => void;
  setActive: (id: string | null) => void;
  createSession: (title?: string) => ChatSession;
  renameSession: (id: string, title: string) => void;
  removeSession: (id: string) => void;
  touch: (id: string) => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  sessions: [],
  activeId: null,
  hydrate: (sessions) => set({ sessions, activeId: sessions[0]?.id ?? null }),
  setActive: (id) => set({ activeId: id }),
  createSession: (title = "新对话") => {
    const session: ChatSession = {
      id: uuid(),
      title,
      updatedAt: dayjs().toISOString(),
    };
    set((s) => ({
      sessions: [session, ...s.sessions],
      activeId: session.id,
    }));
    return session;
  },
  renameSession: (id, title) =>
    set((s) => ({
      sessions: s.sessions.map((x) =>
        x.id === id ? { ...x, title, updatedAt: dayjs().toISOString() } : x,
      ),
    })),
  removeSession: (id) =>
    set((s) => {
      const left = s.sessions.filter((x) => x.id !== id);
      const activeId = s.activeId === id ? (left[0]?.id ?? null) : s.activeId;
      return { sessions: left, activeId };
    }),
  touch: (id) =>
    set((s) => ({
      sessions: s.sessions.map((x) =>
        x.id === id ? { ...x, updatedAt: dayjs().toISOString() } : x,
      ),
    })),
}));

/** 选取当前会话；不存在返回 null。 */
export const useActiveSession = (): ChatSession | null => {
  const { sessions, activeId } = useSessionStore();
  return sessions.find((s) => s.id === activeId) ?? null;
};
