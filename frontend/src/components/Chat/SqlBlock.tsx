import { useState } from "react";
import { Button, Space, Tooltip, message } from "antd";
import { CheckOutlined, CopyOutlined } from "@ant-design/icons";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";

interface Props {
  sql: string;
  title?: string;
  showLineNumbers?: boolean;
}

export default function SqlBlock({
  sql,
  title = "SQL",
  showLineNumbers = true,
}: Props): JSX.Element {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      message.success("已复制 SQL");
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      message.error("复制失败");
    }
  };

  return (
    <div
      style={{
        border: "1px solid #e5e7eb",
        borderRadius: 8,
        overflow: "hidden",
        background: "#f8fafc",
        marginTop: 8,
      }}
    >
      <div
        style={{
          padding: "6px 12px",
          background: "#eef2f7",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: 12,
          color: "#374151",
        }}
      >
        <Space size={4}>
          <span style={{ fontWeight: 600 }}>{title}</span>
          <span style={{ color: "#9ca3af" }}>· 校验通过</span>
        </Space>
        <Tooltip title={copied ? "已复制" : "复制"}>
          <Button
            type="text"
            size="small"
            icon={copied ? <CheckOutlined /> : <CopyOutlined />}
            onClick={handleCopy}
          />
        </Tooltip>
      </div>
      <SyntaxHighlighter
        language="sql"
        style={oneLight}
        showLineNumbers={showLineNumbers}
        customStyle={{
          margin: 0,
          padding: 12,
          fontSize: 12.5,
          background: "transparent",
        }}
        wrapLongLines
      >
        {sql.trim()}
      </SyntaxHighlighter>
    </div>
  );
}
