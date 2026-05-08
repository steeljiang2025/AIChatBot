import { useState } from "react";
import { useNavigate, useLocation, useSearchParams } from "react-router-dom";
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
import {
  LockOutlined,
  UserOutlined,
  ThunderboltFilled,
  TeamOutlined,
  MailOutlined,
} from "@ant-design/icons";
import { mockLogin, loginWithBackend, useMockAuth } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";

const { Title, Text } = Typography;

interface MockLoginValues {
  username: string;
  password: string;
}

interface RealLoginValues {
  tenant_code: string;
  email: string;
  password: string;
}

export default function LoginPage(): JSX.Element {
  const navigate = useNavigate();
  const location = useLocation();
  const setSession = useAuthStore((s) => s.setSession);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mockAuth = useMockAuth();

  const [searchParams] = useSearchParams();
  const expiredBy401 = searchParams.get("reason") === "401";

  const from = (location.state as { from?: string } | null)?.from ?? "/workspace";

  const onFinishMock = async (values: MockLoginValues) => {
    setSubmitting(true);
    setError(null);
    try {
      const { token, user, refreshToken } = await mockLogin(values);
      setSession(token, user, refreshToken);
      navigate(from, { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const onFinishReal = async (values: RealLoginValues) => {
    setSubmitting(true);
    setError(null);
    try {
      const { token, user, refreshToken } = await loginWithBackend({
        tenant_code: values.tenant_code.trim(),
        email: values.email.trim(),
        password: values.password,
      });
      setSession(token, user, refreshToken);
      navigate(from, { replace: true });
    } catch (e) {
      const msg =
        e && typeof e === "object" && "response" in e
          ? (e as { response?: { status?: number } }).response?.status === 401
            ? "租户代码、邮箱或密码不正确"
            : "登录失败，请检查网络与后端服务"
          : e instanceof Error
            ? e.message
            : String(e);
      setError(msg);
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
            {mockAuth ? (
              <Text type="secondary">
                Phase 4：本地 mock 登录（<code>VITE_USE_MOCK_AUTH</code> 未设为{" "}
                <code>false</code>）：<code>admin / admin</code> 或{" "}
                <code>demo / demo</code>。
              </Text>
            ) : (
              <Text type="secondary">
                对接真实后端：字段与 <code>POST /auth/login</code> 一致（
                <code>tenant_code</code>、<code>email</code>、<code>password</code>
                ），成功后使用 <code>access_token</code> 调用 <code>/auth/me</code>
                。
              </Text>
            )}
            {expiredBy401 && (
              <Alert
                type="warning"
                showIcon
                message="登录已失效或未授权，请重新登录"
                style={{ marginBottom: 8 }}
              />
            )}
            {error && <Alert type="error" showIcon message={error} />}
            {mockAuth ? (
              <Form<MockLoginValues>
                layout="vertical"
                onFinish={onFinishMock}
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
            ) : (
              <Form<RealLoginValues>
                layout="vertical"
                onFinish={onFinishReal}
                initialValues={{ tenant_code: "", email: "", password: "" }}
                requiredMark={false}
              >
                <Form.Item
                  name="tenant_code"
                  label="租户代码 tenant_code"
                  rules={[{ required: true, message: "请输入租户代码" }]}
                >
                  <Input
                    prefix={<TeamOutlined />}
                    size="large"
                    placeholder="与 meta.tenants.code 一致"
                    autoComplete="organization"
                  />
                </Form.Item>
                <Form.Item
                  name="email"
                  label="邮箱 email"
                  rules={[
                    { required: true, message: "请输入邮箱" },
                    { type: "email", message: "邮箱格式不正确" },
                  ]}
                >
                  <Input
                    prefix={<MailOutlined />}
                    size="large"
                    placeholder="name@company.com"
                    autoComplete="email"
                  />
                </Form.Item>
                <Form.Item
                  name="password"
                  label="密码 password"
                  rules={[{ required: true, message: "请输入密码" }]}
                >
                  <Input.Password
                    prefix={<LockOutlined />}
                    size="large"
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
            )}
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
