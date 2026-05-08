import { useState } from "react";
import { Button, Input, Space, Typography } from "antd";
import { SendOutlined, StopOutlined } from "@ant-design/icons";

const { Text } = Typography;
const { TextArea } = Input;

interface Props {
  /** 当前是否在流式生成 */
  streaming: boolean;
  /** 发送一条消息（提交后清空输入） */
  onSubmit: (text: string) => void;
  /** 中止流式生成 */
  onAbort: () => void;
  disabled?: boolean;
  placeholder?: string;
}

export default function Composer({
  streaming,
  onSubmit,
  onAbort,
  disabled,
  placeholder = "用日常中文问问数据，例如：上个月各产品销售额。Enter 发送，Shift+Enter 换行。",
}: Props): JSX.Element {
  const [value, setValue] = useState("");

  const submit = () => {
    const text = value.trim();
    if (!text || streaming) return;
    onSubmit(text);
    setValue("");
  };

  return (
    <div style={{ borderTop: "1px solid #f1f3f7", padding: 12 }}>
      <TextArea
        autoSize={{ minRows: 2, maxRows: 6 }}
        placeholder={placeholder}
        value={value}
        disabled={disabled || streaming}
        onChange={(e) => setValue(e.target.value)}
        onPressEnter={(e) => {
          if (!e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        style={{ resize: "none" }}
      />
      <Space
        style={{
          width: "100%",
          justifyContent: "space-between",
          marginTop: 8,
        }}
      >
        <Text type="secondary" style={{ fontSize: 12 }}>
          {streaming ? "AI 正在生成回答…" : "Enter 发送，Shift+Enter 换行"}
        </Text>
        {streaming ? (
          <Button danger icon={<StopOutlined />} onClick={onAbort}>
            停止生成
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            disabled={!value.trim() || disabled}
            onClick={submit}
          >
            发送
          </Button>
        )}
      </Space>
    </div>
  );
}
