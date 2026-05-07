import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import HealthCheck from "../pages/HealthCheck";

vi.mock("../api/health", () => ({
  fetchHealth: vi.fn(async () => ({
    status: "ok",
    version: "0.1.0",
    env: "dev",
    db: { meta: "ok", biz: "ok" },
  })),
}));

describe("HealthCheck page", () => {
  it("加载完成后展示 OK 徽标与版本信息", async () => {
    render(
      <MemoryRouter>
        <HealthCheck />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText(/后端 · OK/)).toBeInTheDocument();
    });

    expect(screen.getByText("0.1.0")).toBeInTheDocument();
    expect(screen.getAllByText(/OK/).length).toBeGreaterThanOrEqual(3);
  });
});
