import { useEffect } from "react";
import { Layout, Avatar, Dropdown, Space, Tag, Tooltip, Typography, Button } from "antd";
import { LogoutOutlined, ThunderboltFilled, UserOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { useSessionStore } from "@/store/sessionStore";
import SessionList from "@/components/Sidebar/SessionList";
import ChatArea from "@/components/Chat/ChatArea";
import ChartPanel from "@/components/Chart/ChartPanel";
import { seedDemoSessions } from "@/mocks/seed";

const { Header } = Layout;
const { Text } = Typography;

export default function Workspace(): JSX.Element {
  const user = useAuthStore((s) => s.user);
  const clear = useAuthStore((s) => s.clear);
  const navigate = useNavigate();
  const sessions = useSessionStore((s) => s.sessions);
  const hydrate = useSessionStore((s) => s.hydrate);

  useEffect(() => {
    if (sessions.length === 0) hydrate(seedDemoSessions());
  }, [sessions.length, hydrate]);

  const handleLogout = () => {
    clear();
    navigate("/login", { replace: true });
  };

  return (
    <Layout style={{ minHeight: "100vh", background: "#f5f7fb" }}>
      <Header style={styles.header}>
        <Space size={12} align="center">
          <ThunderboltFilled style={{ fontSize: 22, color: "#1677ff" }} />
          <Text strong style={{ fontSize: 16 }}>
            AIChatBot · 智能数据分析助理
          </Text>
          <Tag color="processing">Phase 2 · Mock 驱动</Tag>
        </Space>
        <Space size={12}>
          <Tooltip title={`租户：${user?.tenantId ?? "-"}`}>
            <Tag color="geekblue">{user?.tenantId ?? "tenant"}</Tag>
          </Tooltip>
          <Dropdown
            menu={{
              items: [
                {
                  key: "logout",
                  icon: <LogoutOutlined />,
                  label: "退出登录",
                  onClick: handleLogout,
                },
              ],
            }}
          >
            <Button type="text">
              <Space>
                <Avatar size="small" icon={<UserOutlined />} />
                {user?.displayName ?? user?.username ?? "用户"}
              </Space>
            </Button>
          </Dropdown>
        </Space>
      </Header>

      <Layout.Content style={styles.content}>
        <aside style={styles.sidebar}>
          <SessionList />
        </aside>
        <main style={styles.main}>
          <ChatArea />
        </main>
        <aside style={styles.right}>
          <ChartPanel />
        </aside>
      </Layout.Content>
    </Layout>
  );
}

const styles = {
  header: {
    background: "#fff",
    borderBottom: "1px solid #e5e7eb",
    paddingInline: 24,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    height: 56,
    lineHeight: "56px",
  },
  content: {
    display: "grid",
    gridTemplateColumns: "260px 1fr 480px",
    gap: 12,
    padding: 12,
    height: "calc(100vh - 56px)",
    minHeight: 0,
  },
  sidebar: {
    background: "#fff",
    borderRadius: 12,
    border: "1px solid #e5e7eb",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    minHeight: 0,
  } as const,
  main: {
    background: "#fff",
    borderRadius: 12,
    border: "1px solid #e5e7eb",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    minHeight: 0,
  } as const,
  right: {
    background: "#fff",
    borderRadius: 12,
    border: "1px solid #e5e7eb",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    minHeight: 0,
  } as const,
};
