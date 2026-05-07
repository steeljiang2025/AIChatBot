import dayjs from "dayjs";
import { v4 as uuid } from "uuid";
import type { ChatSession } from "@/types/chat";

export function seedDemoSessions(): ChatSession[] {
  const now = dayjs();
  return [
    {
      id: uuid(),
      title: "上个月各产品销售额",
      updatedAt: now.toISOString(),
    },
    {
      id: uuid(),
      title: "周度活跃用户走势",
      updatedAt: now.subtract(1, "day").toISOString(),
    },
    {
      id: uuid(),
      title: "Top 10 客户订单分布",
      updatedAt: now.subtract(3, "day").toISOString(),
    },
  ];
}
