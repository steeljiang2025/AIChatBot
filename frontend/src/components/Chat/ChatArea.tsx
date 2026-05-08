import { useEffect } from "react";
import { Empty, Space, Tag, Typography, message } from "antd";
import { useActiveSession } from "@/store/sessionStore";
import { useChatStore } from "@/store/chatStore";
import { useChatStream } from "@/hooks/useChatStream";
import { fetchSessionMessages } from "@/api/sessions";
import { mapMessageApiToChatMessage } from "@/api/mappers";
import type { ChatMessage } from "@/types/chat";
import MessageList from "./MessageList";
import Composer from "./Composer";

const { Text } = Typography;

const EMPTY_MESSAGES: ChatMessage[] = [];

interface Props {
  /** true：切换会话时从 GET /sessions/:id/messages 拉历史 */
  loadHistory: boolean;
}

export default function ChatArea({ loadHistory }: Props): JSX.Element {
  const session = useActiveSession();
  const sessionId = session?.id;
  const messages = useChatStore((s) =>
    sessionId ? (s.messagesBySession[sessionId] ?? EMPTY_MESSAGES) : EMPTY_MESSAGES,
  );
  const streamingId = useChatStore((s) =>
    sessionId ? s.streamingMessageId[sessionId] : undefined,
  );
  const replaceSessionMessages = useChatStore((s) => s.replaceSessionMessages);
  const { send, abort } = useChatStream();

  useEffect(() => {
    if (!loadHistory || !sessionId) return;
    const sid = sessionId;
    let cancelled = false;
    (async () => {
      try {
        const list = await fetchSessionMessages(sid, { limit: 200, offset: 0 });
        if (cancelled) return;
        const mapped = list.items.map(mapMessageApiToChatMessage);
        replaceSessionMessages(sid, mapped);
      } catch {
        if (!cancelled) {
          message.error("加载历史消息失败");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadHistory, sessionId, replaceSessionMessages]);

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
