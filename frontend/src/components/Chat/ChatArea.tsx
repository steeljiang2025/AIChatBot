import { Empty, Space, Tag, Typography } from "antd";
import { useActiveSession } from "@/store/sessionStore";
import { useChatStore } from "@/store/chatStore";
import { useChatStream } from "@/hooks/useChatStream";
import type { ChatMessage } from "@/types/chat";
import MessageList from "./MessageList";
import Composer from "./Composer";

const { Text } = Typography;

const EMPTY_MESSAGES: ChatMessage[] = [];

export default function ChatArea(): JSX.Element {
  const session = useActiveSession();
  const sessionId = session?.id;
  const messages = useChatStore((s) =>
    sessionId ? (s.messagesBySession[sessionId] ?? EMPTY_MESSAGES) : EMPTY_MESSAGES,
  );
  const streamingId = useChatStore((s) =>
    sessionId ? s.streamingMessageId[sessionId] : undefined,
  );
  const { send, abort } = useChatStream();

  if (!session) {
    return (
      <div style={{ flex: 1, display: "grid", placeItems: "center", padding: 24 }}>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="请在左侧新建或选择一个会话"
        />
      </div>
    );
  }

  const streaming = Boolean(streamingId);

  return (
    <>
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #f1f3f7",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Space size={8}>
          <Text strong>{session.title}</Text>
          <Tag color="blue">{messages.length} 条消息</Tag>
        </Space>
        {streaming && <Tag color="processing">流式生成中</Tag>}
      </div>
      <MessageList messages={messages} />
      <Composer
        streaming={streaming}
        onSubmit={(text) => send(session.id, text)}
        onAbort={() => abort(session.id)}
      />
    </>
  );
}
