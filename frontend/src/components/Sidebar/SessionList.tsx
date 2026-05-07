import { useMemo, useState } from "react";
import {
  Button,
  Empty,
  Input,
  Modal,
  Popconfirm,
  Space,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  MessageOutlined,
} from "@ant-design/icons";
import dayjs from "dayjs";
import classNames from "classnames";
import { useSessionStore } from "@/store/sessionStore";
import type { ChatSession } from "@/types/chat";
import "./SessionList.css";

const { Text } = Typography;

type Group = "today" | "yesterday" | "earlier";

const GROUP_LABEL: Record<Group, string> = {
  today: "今天",
  yesterday: "昨天",
  earlier: "更早",
};

function groupKey(s: ChatSession): Group {
  const d = dayjs(s.updatedAt);
  const today = dayjs().startOf("day");
  if (d.isSame(today, "day")) return "today";
  if (d.isSame(today.subtract(1, "day"), "day")) return "yesterday";
  return "earlier";
}

export default function SessionList(): JSX.Element {
  const sessions = useSessionStore((s) => s.sessions);
  const activeId = useSessionStore((s) => s.activeId);
  const setActive = useSessionStore((s) => s.setActive);
  const createSession = useSessionStore((s) => s.createSession);
  const renameSession = useSessionStore((s) => s.renameSession);
  const removeSession = useSessionStore((s) => s.removeSession);

  const [renameTarget, setRenameTarget] = useState<ChatSession | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const grouped = useMemo(() => {
    const m: Record<Group, ChatSession[]> = { today: [], yesterday: [], earlier: [] };
    sessions
      .slice()
      .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
      .forEach((s) => m[groupKey(s)].push(s));
    return m;
  }, [sessions]);

  const handleNew = () => {
    const s = createSession();
    message.success(`已创建会话「${s.title}」`);
  };

  const openRename = (s: ChatSession) => {
    setRenameTarget(s);
    setRenameValue(s.title);
  };
  const submitRename = () => {
    if (!renameTarget) return;
    const v = renameValue.trim();
    if (!v) return;
    renameSession(renameTarget.id, v);
    setRenameTarget(null);
  };

  return (
    <div className="session-list">
      <div className="session-list__header">
        <Text strong>会话</Text>
        <Button
          size="small"
          type="primary"
          icon={<PlusOutlined />}
          onClick={handleNew}
        >
          新建
        </Button>
      </div>

      <div className="session-list__body">
        {sessions.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无会话" />
        ) : (
          (Object.keys(grouped) as Group[]).map((g) =>
            grouped[g].length === 0 ? null : (
              <div key={g} className="session-list__group">
                <div className="session-list__group-title">{GROUP_LABEL[g]}</div>
                <Space direction="vertical" size={4} style={{ width: "100%" }}>
                  {grouped[g].map((s) => (
                    <div
                      key={s.id}
                      className={classNames("session-item", {
                        "session-item--active": activeId === s.id,
                      })}
                      onClick={() => setActive(s.id)}
                    >
                      <MessageOutlined className="session-item__icon" />
                      <div className="session-item__title">{s.title}</div>
                      <Space size={2} className="session-item__actions">
                        <Tooltip title="重命名">
                          <Button
                            type="text"
                            size="small"
                            icon={<EditOutlined />}
                            onClick={(e) => {
                              e.stopPropagation();
                              openRename(s);
                            }}
                          />
                        </Tooltip>
                        <Popconfirm
                          title="删除该会话？"
                          okType="danger"
                          okText="删除"
                          cancelText="取消"
                          onConfirm={(e) => {
                            e?.stopPropagation();
                            removeSession(s.id);
                          }}
                          onCancel={(e) => e?.stopPropagation()}
                        >
                          <Button
                            type="text"
                            size="small"
                            icon={<DeleteOutlined />}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </Popconfirm>
                      </Space>
                    </div>
                  ))}
                </Space>
              </div>
            ),
          )
        )}
      </div>

      <Modal
        title="重命名会话"
        open={renameTarget !== null}
        onCancel={() => setRenameTarget(null)}
        onOk={submitRename}
        okText="保存"
        cancelText="取消"
        destroyOnHidden
      >
        <Input
          autoFocus
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onPressEnter={submitRename}
          maxLength={50}
        />
      </Modal>
    </div>
  );
}
