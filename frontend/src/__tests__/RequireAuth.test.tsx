import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import RequireAuth from "@/components/RequireAuth";
import { useAuthStore } from "@/store/authStore";

function setup(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<div>登录页</div>} />
        <Route
          path="/workspace"
          element={
            <RequireAuth>
              <div>工作区内容</div>
            </RequireAuth>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireAuth", () => {
  beforeEach(() => {
    useAuthStore.setState({ token: null, user: null });
  });

  it("未登录访问 /workspace 时跳转登录页", () => {
    setup("/workspace");
    expect(screen.getByText("登录页")).toBeInTheDocument();
  });

  it("已登录则放行进入工作区", () => {
    useAuthStore.setState({
      token: "fake.token",
      user: {
        id: "u1",
        username: "u1",
        displayName: "u1",
        tenantId: "t1",
        roles: ["x"],
      },
    });
    setup("/workspace");
    expect(screen.getByText("工作区内容")).toBeInTheDocument();
  });
});
