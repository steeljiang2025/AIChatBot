import { useState } from "react";
import { Collapse, Space, Tag, Typography } from "antd";
import {
  CheckCircleFilled,
  ClockCircleFilled,
  CloseCircleFilled,
  LoadingOutlined,
} from "@ant-design/icons";
import type { NodeStatus, ThinkingNode } from "@/types/chat";

const { Text } = Typography;

const STATUS_COLOR: Record<NodeStatus, string> = {
  pending: "#9ca3af",
  running: "#1677ff",
  ok: "#10b981",
  error: "#ef4444",
};

function StatusIcon({ status }: { status: NodeStatus }): JSX.Element {
  switch (status) {
    case "running":
      return <LoadingOutlined style={{ color: STATUS_COLOR.running }} spin />;
    case "ok":
      return <CheckCircleFilled style={{ color: STATUS_COLOR.ok }} />;
    case "error":
      return <CloseCircleFilled style={{ color: STATUS_COLOR.error }} />;
    case "pending":
    default:
      return <ClockCircleFilled style={{ color: STATUS_COLOR.pending }} />;
  }
}

interface Props {
  nodes: ThinkingNode[];
  defaultActive?: boolean;
}

export default function ThinkingTrace({
  nodes,
  defaultActive = false,
}: Props): JSX.Element | null {
  const [active, setActive] = useState<string[]>(defaultActive ? ["trace"] : []);
  if (!nodes || nodes.length === 0) return null;

  const summary = nodes.some((n) => n.status === "running")
    ? "思考中…"
    : nodes.every((n) => n.status === "ok")
      ? "思考完成"
      : nodes.some((n) => n.status === "error")
        ? "思考过程出现错误"
        : "思考过程";

  return (
    <Collapse
      size="small"
      activeKey={active}
      onChange={(keys) => setActive(Array.isArray(keys) ? keys : [keys])}
      style={{ marginTop: 8, background: "#fafbfd", borderRadius: 8 }}
      items={[
        {
          key: "trace",
          label: (
            <Space size={8}>
              <Text type="secondary" style={{ fontSize: 12 }}>
                {summary}
              </Text>
              <Tag color="blue">{nodes.length} 步</Tag>
            </Space>
          ),
          children: (
            <Space direction="vertical" size={6} style={{ width: "100%" }}>
              {nodes.map((n) => (
                <div
                  key={n.name}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    fontSize: 12,
                  }}
                >
                  <StatusIcon status={n.status} />
                  <span style={{ color: "#1f2937", minWidth: 92 }}>{n.label}</span>
                  {n.detail && (
                    <span style={{ color: "#6b7280", fontSize: 11 }}>{n.detail}</span>
                  )}
                </div>
              ))}
            </Space>
          ),
        },
      ]}
    />
  );
}
