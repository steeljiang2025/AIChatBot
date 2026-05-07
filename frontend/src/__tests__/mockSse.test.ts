import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { startMockStream } from "@/mocks/sseServer";
import type { SseEnvelope } from "@/types/chat";

describe("mock SSE server", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("依次 emit 节点 → SQL → rows → chart → token → done", async () => {
    const events: SseEnvelope[] = [];
    startMockStream("上个月各产品销售额", {
      onEvent: (e) => events.push(e),
    });
    await vi.runAllTimersAsync();

    const names = events.map((e) => e.event);
    expect(names).toContain("node");
    expect(names).toContain("sql");
    expect(names).toContain("rows");
    expect(names).toContain("chart");
    expect(names).toContain("token");
    expect(names[names.length - 1]).toBe("done");
  });

  it("abort 后不再 emit 后续事件", async () => {
    const events: SseEnvelope[] = [];
    const handle = startMockStream("hello", {
      onEvent: (e) => events.push(e),
    });
    handle.abort();
    await vi.runAllTimersAsync();
    expect(events).toHaveLength(0);
  });
});
