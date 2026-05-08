import { describe, expect, it, beforeEach } from "vitest";
import { useSessionStore } from "@/store/sessionStore";

describe("sessionStore", () => {
  beforeEach(() => {
    useSessionStore.setState({ sessions: [], activeId: null });
  });

  it("createSession 添加并设为当前会话", () => {
    const s = useSessionStore.getState().createSession("hello");
    expect(useSessionStore.getState().sessions).toHaveLength(1);
    expect(useSessionStore.getState().activeId).toBe(s.id);
    expect(s.title).toBe("hello");
  });

  it("renameSession 更新标题", () => {
    const s = useSessionStore.getState().createSession();
    useSessionStore.getState().renameSession(s.id, "新标题");
    expect(useSessionStore.getState().sessions[0].title).toBe("新标题");
  });

  it("prependSession 插入并激活", () => {
    useSessionStore.getState().createSession("a");
    const s2 = { id: "id-2", title: "b", updatedAt: new Date().toISOString() };
    useSessionStore.getState().prependSession(s2);
    expect(useSessionStore.getState().activeId).toBe("id-2");
    expect(useSessionStore.getState().sessions[0].title).toBe("b");
  });

  it("replaceSessions 可指定 activeId", () => {
    useSessionStore.getState().createSession("a");
    useSessionStore.getState().createSession("b");
    useSessionStore.getState().replaceSessions(
      [
        { id: "x1", title: "X1", updatedAt: new Date().toISOString() },
        { id: "x2", title: "X2", updatedAt: new Date().toISOString() },
      ],
      "x2",
    );
    expect(useSessionStore.getState().activeId).toBe("x2");
    expect(useSessionStore.getState().sessions).toHaveLength(2);
  });

  it("removeSession 移除并切到下一个", () => {
    const s1 = useSessionStore.getState().createSession("一");
    const s2 = useSessionStore.getState().createSession("二");
    useSessionStore.getState().setActive(s1.id);
    useSessionStore.getState().removeSession(s1.id);
    expect(useSessionStore.getState().sessions).toHaveLength(1);
    expect(useSessionStore.getState().activeId).toBe(s2.id);
  });
});
