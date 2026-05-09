import { useCallback, useEffect, useState } from "react";
import { Alert, Button, Card, Descriptions, Space, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";

import { fetchHealth, type HealthResponse } from "../api/health";
import HealthBadge, { type Status } from "../components/HealthBadge";

const { Text } = Typography;

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

      <Card title="服务能力">
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="认证">
            <Text code>/auth</Text>
          </Descriptions.Item>
          <Descriptions.Item label="会话">
            <Text code>/sessions</Text>
          </Descriptions.Item>
          <Descriptions.Item label="流式分析">
            <Text code>/chat/stream</Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>
    </Space>
  );
}
