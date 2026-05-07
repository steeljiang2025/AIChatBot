import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  Layout,
  Space,
  Typography,
} from "antd";
import { LockOutlined, UserOutlined, ThunderboltFilled } from "@ant-design/icons";
import { mockLogin } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";

const { Title, Text } = Typography;

interface LoginValues {
  username: string;
  password: string;
}

export default function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((s) => s.setSession);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as { from?: string } | null)?.from ?? "/workspace";

  const onFinish = async (values: LoginValues) => {
    setSubmitting(true);
    setError(null);
    try {
      const { token, user } = await mockLogin(values);
      setSession(token, user);
      navigate(from, { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Layout style={styles.layout}>
      <Layout.Content style={styles.content}>
        <Card style={styles.card} variant="borderless">
          <Space direction="vertical" size={24} style={{ width: "100%" }}>
            <Space align="center" size={12}>
              <ThunderboltFilled style={{ fontSize: 28, color: "#1677ff" }} />
              <Title level={3} style={{ margin: 0 }}>
                AIChatBot · 智能数据分析助理
              </Title>
            </Space>
            <Text type="secondary">
              用日常中文提问，让 AI 帮你查数据、画图表、做总结。Phase 2 使用 mock
              账号登录：<code>admin / admin</code> 或 <code>demo / demo</code>。
            </Text>
            {error && <Alert type="error" showIcon message={error} />}
            <Form<LoginValues>
              layout="vertical"
              onFinish={onFinish}
              initialValues={{ username: "admin", password: "admin" }}
              requiredMark={false}
            >
              <Form.Item
                name="username"
                label="用户名"
                rules={[{ required: true, message: "请输入用户名" }]}
              >
                <Input
                  prefix={<UserOutlined />}
                  size="large"
                  placeholder="admin / demo"
                  autoComplete="username"
                />
              </Form.Item>
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: "请输入密码" }]}
              >
                <Input.Password
                  prefix={<LockOutlined />}
                  size="large"
                  placeholder="admin / demo"
                  autoComplete="current-password"
                />
              </Form.Item>
              <Form.Item style={{ marginBottom: 0 }}>
                <Button
                  type="primary"
                  htmlType="submit"
                  size="large"
                  loading={submitting}
                  block
                >
                  登 录
                </Button>
              </Form.Item>
            </Form>
          </Space>
        </Card>
      </Layout.Content>
    </Layout>
  );
}

const styles = {
  layout: {
    minHeight: "100vh",
    background:
      "radial-gradient(circle at 20% 20%, #c7d2fe 0, transparent 40%)," +
      "radial-gradient(circle at 80% 30%, #fce7f3 0, transparent 40%)," +
      "linear-gradient(135deg, #f5f7fb 0%, #e6efff 100%)",
  },
  content: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 24,
  },
  card: {
    width: 420,
    boxShadow: "0 12px 32px rgba(15, 23, 42, 0.12)",
    borderRadius: 16,
  },
} as const;
