import { Tag, Tooltip } from "antd";
import { CheckCircleFilled, CloseCircleFilled, LoadingOutlined } from "@ant-design/icons";

export type Status = "loading" | "ok" | "down";

interface Props {
  label: string;
  status: Status;
  hint?: string;
}

export default function HealthBadge({ label, status, hint }: Props) {
  const tag =
    status === "loading" ? (
      <Tag icon={<LoadingOutlined />} color="processing">
        {label} · 检测中
      </Tag>
    ) : status === "ok" ? (
      <Tag icon={<CheckCircleFilled />} color="success">
        {label} · OK
      </Tag>
    ) : (
      <Tag icon={<CloseCircleFilled />} color="error">
        {label} · 异常
      </Tag>
    );

  return hint ? <Tooltip title={hint}>{tag}</Tooltip> : tag;
}
