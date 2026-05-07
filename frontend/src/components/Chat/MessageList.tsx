import { useEffect, useRef } from "react";
import { Empty } from "antd";
import type { ChatMessage } from "@/types/chat";
import MessageBubble from "./MessageBubble";

interface Props {
  messages: ChatMessage[];
}

export default function MessageList({ messages }: Props): JSX.Element {
  const tailRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    tailRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div style={{ flex: 1, display: "grid", placeItems: "center", padding: 24 }}>
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="开个口问问，比如：上个月各产品销售额"
        />
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "16px 24px" }}>
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      <div ref={tailRef} />
    </div>
  );
}
