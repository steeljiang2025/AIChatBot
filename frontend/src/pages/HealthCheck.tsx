import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Descriptions, Space, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";

import { fetchHealth, type HealthResponse } from "../api/health";
import HealthBadge, { type Status } from "../components/HealthBadge";

const { Paragraph, Text } = Typography;

interface State {
  loading: boolean;
  data?: HealthResponse;
  error?: string;
}

const initial: State = { loading: true };

export default function HealthCheck() {
  const [state, setState] = useState<State>(initial);

  const load = useCallback(async () => {
    setState({ loading: true });
    try {
      const data = await fetchHealth();
      setState({ loading: false, data });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setState({ loading: false, error: msg });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const overall: Status = state.loading
    ? "loading"
    : state.data?.status === "ok"
      ? "ok"
      : "down";

  const meta: Status = state.loading
    ? "loading"
    : state.data?.db.meta === "ok"
      ? "ok"
      : "down";

  const biz: Status = state.loading
    ? "loading"
    : state.data?.db.biz === "ok"
      ? "ok"
      : "down";

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      <Card
        title="后端连接 / 数据库探针"
        extra={
          <Button icon={<ReloadOutlined />} onClick={load} loading={state.loading}>
            重新检测
          </Button>
        }
      >
        <Space size="middle" wrap>
          <HealthBadge label="后端" status={overall} hint="GET /api/health" />
          <HealthBadge label="meta DB" status={meta} hint="应用元数据库" />
          <HealthBadge label="biz DB" status={biz} hint="业务库（只读账号）" />
        </Space>

        {state.error && (
          <Alert style={{ marginTop: 16 }} type="error" showIcon message="请求失败" description={state.error} />
        )}

        {state.data && (
          <Descriptions column={1} style={{ marginTop: 24 }} size="small" bordered>
            <Descriptions.Item label="版本">
              <Text code>{state.data.version}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="环境">{state.data.env}</Descriptions.Item>
            <Descriptions.Item label="整体状态">{state.data.status}</Descriptions.Item>
          </Descriptions>
        )}
      </Card>

      <Card title="下一步">
        <Paragraph>
          Phase 4 已完成前后端联调：Workspace 使用真实{" "}
          <Text code>/auth</Text>、<Text code>/sessions</Text>、
          <Text code>/chat/stream</Text>（JWT + SSE）。Mock 账号仍可用于无后端环境的 UI
          演示；真实 JWT 下自动拉取会话与历史消息。详见仓库根目录{" "}
          <Text code>README.md</Text>「Phase 4」一节。
        </Paragraph>
      </Card>
    </Space>
  );
}
