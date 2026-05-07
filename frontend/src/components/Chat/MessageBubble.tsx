import { Avatar, Space, Tag, Typography } from "antd";
import { RobotOutlined, UserOutlined } from "@ant-design/icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import "highlight.js/styles/github.css";
import dayjs from "dayjs";
import type { ChatMessage } from "@/types/chat";
import SqlBlock from "./SqlBlock";
import ThinkingTrace from "./ThinkingTrace";

const { Text } = Typography;

interface Props {
  message: ChatMessage;
}

export default function MessageBubble({ message }: Props): JSX.Element {
  const isUser = message.role === "user";
  return (
    <div
      style={{
        display: "flex",
        gap: 12,
        marginBottom: 16,
        flexDirection: isUser ? "row-reverse" : "row",
      }}
    >
      <Avatar
        icon={isUser ? <UserOutlined /> : <RobotOutlined />}
        style={{
          backgroundColor: isUser ? "#1677ff" : "#10b981",
          flexShrink: 0,
        }}
      />
      <div
        style={{
          maxWidth: "min(640px, 80%)",
          display: "flex",
          flexDirection: "column",
          alignItems: isUser ? "flex-end" : "flex-start",
        }}
      >
        <Space size={8} style={{ marginBottom: 4 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {dayjs(message.createdAt).format("HH:mm:ss")}
          </Text>
          {message.streaming && <Tag color="processing">生成中</Tag>}
          {message.error && <Tag color="error">{message.error.code}</Tag>}
        </Space>
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 12,
            background: isUser ? "#1677ff" : "#f5f7fb",
            color: isUser ? "#fff" : "#1f2937",
            boxShadow: isUser ? "none" : "0 1px 2px rgba(0,0,0,0.04)",
            width: "fit-content",
            maxWidth: "100%",
            wordBreak: "break-word",
            lineHeight: 1.7,
          }}
          className={isUser ? "bubble bubble-user" : "bubble bubble-assistant"}
        >
          {isUser ? (
            <div style={{ whiteSpace: "pre-wrap" }}>{message.content}</div>
          ) : (
            <div className="markdown-body">
              {message.content ? (
                <ReactMarkdownRender content={message.content} />
              ) : message.streaming ? (
                <Text type="secondary">正在思考…</Text>
              ) : message.error ? (
                <Text type="danger">{message.error.message}</Text>
              ) : null}
            </div>
          )}
        </div>
        {!isUser && (
          <div style={{ width: "100%" }}>
            {message.thinking && message.thinking.length > 0 && (
              <ThinkingTrace nodes={message.thinking} />
            )}
            {message.sql && <SqlBlock sql={message.sql} />}
          </div>
        )}
      </div>
    </div>
  );
}

function ReactMarkdownRender({ content }: { content: string }): JSX.Element | null {
  if (!content) return null;
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={{
        a: ({ children, ...props }) => (
          <a {...props} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
        table: ({ children }) => (
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", width: "100%" }}>
              {children}
            </table>
          </div>
        ),
        th: ({ children }) => (
          <th
            style={{
              border: "1px solid #e5e7eb",
              padding: "6px 8px",
              background: "#f3f4f6",
              textAlign: "left",
            }}
          >
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td style={{ border: "1px solid #e5e7eb", padding: "6px 8px" }}>
            {children}
          </td>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
