// =============================================================
// Phase 2 dev-only Mock SSE 服务器
//
// 给定用户问题，按 SSE 协议模拟一整段对话流：
//   node(running) -> ... -> node(ok)
//   token x N（流式文字）
//   sql / rows / chart / done
//
// 用法：
//   const stream = startMockStream("上个月各产品销售额", { onEvent });
//   stream.abort();  // 用户主动停止
// =============================================================

import type { ChartSpec, RowsPayload, SseEnvelope } from "@/types/chat";

export interface MockStreamOptions {
  onEvent: (env: SseEnvelope) => void;
  onDone?: () => void;
  /** token 之间的间隔毫秒，默认 28ms */
  tokenInterval?: number;
}

export interface MockStreamHandle {
  abort: () => void;
}

interface Scenario {
  /** 命中关键词；空数组表示通用兜底 */
  keywords: string[];
  /** 回答正文（Markdown） */
  answer: string;
  sql: string;
  rows: RowsPayload;
  chart: ChartSpec;
}

const SCENARIOS: Scenario[] = [
  {
    keywords: ["销售", "产品", "销售额", "上个月", "上月"],
    answer: `根据上月（2026-04）订单数据汇总：

| 产品 | 销售额（元） | 同比 |
| --- | ---: | ---: |
| 智能音箱 | 1,820,300 | +12.4% |
| 扫地机器人 | 1,564,800 | +8.1% |
| 蓝牙耳机 | 982,400 | -3.2% |
| 智能手表 | 845,100 | +5.6% |
| 平板电脑 | 615,200 | +1.0% |

> 智能音箱 + 扫地机器人占比 **48.7%**，是上月最强支柱品类。建议下月对蓝牙耳机做促销。`,
    sql: `SELECT
  p.name        AS product,
  SUM(o.amount) AS sales_amount
FROM biz.orders o
JOIN biz.products p ON p.id = o.product_id
WHERE o.order_date >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
  AND o.order_date <  DATE_TRUNC('month', CURRENT_DATE)
GROUP BY p.name
ORDER BY sales_amount DESC
LIMIT 5;`,
    rows: {
      columns: ["product", "sales_amount", "yoy"],
      data: [
        ["智能音箱", 1820300, 0.124],
        ["扫地机器人", 1564800, 0.081],
        ["蓝牙耳机", 982400, -0.032],
        ["智能手表", 845100, 0.056],
        ["平板电脑", 615200, 0.01],
      ],
    },
    chart: {
      title: { text: "上月各产品销售额", left: "left" },
      tooltip: { trigger: "axis" },
      grid: { left: 60, right: 24, top: 48, bottom: 36 },
      xAxis: {
        type: "category",
        data: ["智能音箱", "扫地机器人", "蓝牙耳机", "智能手表", "平板电脑"],
      },
      yAxis: { type: "value", name: "销售额（元）" },
      series: [
        {
          type: "bar",
          data: [1820300, 1564800, 982400, 845100, 615200],
          itemStyle: { color: "#1677ff", borderRadius: [6, 6, 0, 0] },
          label: { show: true, position: "top", formatter: "{c}" },
        },
      ],
    },
  },
  {
    keywords: ["活跃", "用户", "周", "wau", "dau"],
    answer: `最近 8 周 WAU 走势：

- 整体保持上行，平均周环比 **+3.6%**
- 最近一周回落 1.2%，主要受春节假期影响（去年同期同比仍 +18.1%）`,
    sql: `SELECT
  DATE_TRUNC('week', login_at)::date AS week,
  COUNT(DISTINCT user_id)            AS wau
FROM biz.login_logs
WHERE login_at >= CURRENT_DATE - INTERVAL '8 weeks'
GROUP BY 1
ORDER BY 1;`,
    rows: {
      columns: ["week", "wau"],
      data: [
        ["2026-03-09", 18420],
        ["2026-03-16", 18950],
        ["2026-03-23", 19410],
        ["2026-03-30", 20020],
        ["2026-04-06", 20660],
        ["2026-04-13", 21180],
        ["2026-04-20", 21870],
        ["2026-04-27", 21610],
      ],
    },
    chart: {
      title: { text: "周活跃用户走势（最近 8 周）", left: "left" },
      tooltip: { trigger: "axis" },
      grid: { left: 60, right: 24, top: 48, bottom: 36 },
      xAxis: {
        type: "category",
        data: [
          "03-09",
          "03-16",
          "03-23",
          "03-30",
          "04-06",
          "04-13",
          "04-20",
          "04-27",
        ],
      },
      yAxis: { type: "value", name: "WAU" },
      series: [
        {
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 8,
          areaStyle: { color: "rgba(22,119,255,0.16)" },
          itemStyle: { color: "#1677ff" },
          data: [18420, 18950, 19410, 20020, 20660, 21180, 21870, 21610],
        },
      ],
    },
  },
  {
    keywords: ["客户", "top", "订单"],
    answer: `Top 10 客户订单分布：

- 头部 3 名贡献了 **41%** 总订单额
- 与去年对比，新进客户「未来零售」直接挤进 Top 5`,
    sql: `SELECT
  c.name              AS customer,
  COUNT(o.id)         AS order_cnt,
  SUM(o.amount)       AS order_amount
FROM biz.orders o
JOIN biz.customers c ON c.id = o.customer_id
GROUP BY c.name
ORDER BY order_amount DESC
LIMIT 10;`,
    rows: {
      columns: ["customer", "order_cnt", "order_amount"],
      data: [
        ["晨光科技", 326, 920000],
        ["蓝海集团", 304, 845200],
        ["未来零售", 281, 803100],
        ["华星电子", 247, 612800],
        ["远东仓储", 219, 540500],
        ["翔宇物流", 198, 487300],
        ["新华书友", 173, 421900],
        ["共建工坊", 151, 356400],
        ["云鼎咨询", 132, 298100],
        ["万象传媒", 119, 245700],
      ],
    },
    chart: {
      title: { text: "Top 10 客户订单额", left: "left" },
      tooltip: { trigger: "item" },
      legend: { orient: "vertical", right: 10, top: 30 },
      series: [
        {
          type: "pie",
          radius: ["45%", "75%"],
          center: ["40%", "55%"],
          itemStyle: { borderRadius: 8, borderColor: "#fff", borderWidth: 2 },
          label: { formatter: "{b}: {d}%" },
          data: [
            { name: "晨光科技", value: 920000 },
            { name: "蓝海集团", value: 845200 },
            { name: "未来零售", value: 803100 },
            { name: "华星电子", value: 612800 },
            { name: "远东仓储", value: 540500 },
            { name: "翔宇物流", value: 487300 },
            { name: "新华书友", value: 421900 },
            { name: "共建工坊", value: 356400 },
            { name: "云鼎咨询", value: 298100 },
            { name: "万象传媒", value: 245700 },
          ],
        },
      ],
    },
  },
];

const FALLBACK: Scenario = {
  keywords: [],
  answer: `这是 Phase 2 的 mock 回答。我虚构了一组演示数据，便于看出 SSE 流 → Markdown → SQL 高亮 → 数据表 → ECharts 图表的完整体验。

> 真实接入会在 Phase 3 落地（语义检索 / SQL 安全 / LangGraph 工作流）。`,
  sql: `-- 这是 mock SQL，仅用于演示前端流程
SELECT 1 AS demo;`,
  rows: {
    columns: ["维度", "值"],
    data: [
      ["Phase", "2"],
      ["状态", "Mock 驱动"],
      ["下一步", "Phase 3 真实后端"],
    ],
  },
  chart: {
    title: { text: "Phase 2 占位图", left: "left" },
    xAxis: { type: "category", data: ["A", "B", "C", "D", "E"] },
    yAxis: { type: "value" },
    tooltip: { trigger: "axis" },
    series: [
      {
        type: "bar",
        data: [12, 19, 7, 24, 16],
        itemStyle: { color: "#10b981", borderRadius: [6, 6, 0, 0] },
      },
    ],
  },
};

function pickScenario(prompt: string): Scenario {
  const text = prompt.toLowerCase();
  return (
    SCENARIOS.find((s) => s.keywords.some((k) => text.includes(k.toLowerCase()))) ??
    FALLBACK
  );
}

/** 把字符串拆分成「词」级别的流式 token，便于看出流式效果 */
function tokenize(text: string): string[] {
  // 中文按字、英文按单词，遇到空白或标点后立即切片
  const out: string[] = [];
  let buf = "";
  for (const ch of text) {
    if (/[\u4e00-\u9fa5]/.test(ch)) {
      if (buf) {
        out.push(buf);
        buf = "";
      }
      out.push(ch);
    } else if (/\s/.test(ch) || /[，。、；：！？,.;:!?]/.test(ch)) {
      buf += ch;
      out.push(buf);
      buf = "";
    } else {
      buf += ch;
    }
  }
  if (buf) out.push(buf);
  return out;
}

export function startMockStream(
  prompt: string,
  options: MockStreamOptions,
): MockStreamHandle {
  const { onEvent, onDone, tokenInterval = 28 } = options;
  const scenario = pickScenario(prompt);
  let aborted = false;
  const timers: ReturnType<typeof setTimeout>[] = [];

  const after = (delay: number, fn: () => void) => {
    const t = setTimeout(() => {
      if (!aborted) fn();
    }, delay);
    timers.push(t);
  };

  // —— 节点进度：retrieve -> sql_gen -> sql_validate -> tenant_guard -> sql_exec -> chart -> summarize
  let cursor = 50;
  const node = (
    name:
      | "retrieve"
      | "sql_gen"
      | "sql_validate"
      | "tenant_guard"
      | "sql_exec"
      | "chart"
      | "summarize",
    runDelay: number,
    okDelay: number,
    detail?: string,
  ) => {
    after(cursor, () =>
      onEvent({ event: "node", data: { name, status: "running", detail } }),
    );
    cursor += runDelay;
    after(cursor, () => onEvent({ event: "node", data: { name, status: "ok", detail } }));
    cursor += okDelay;
  };

  node("retrieve", 380, 80, "命中 3 张相关表卡片");
  node("sql_gen", 520, 80, "生成候选 SQL");
  node("sql_validate", 220, 80, "sqlglot 校验通过");
  node("tenant_guard", 180, 80, "已注入 tenant_id");

  // —— SQL
  after(cursor, () => onEvent({ event: "sql", data: { sql: scenario.sql } }));
  cursor += 60;

  // —— 执行节点
  node("sql_exec", 380, 80, `${scenario.rows.data.length} 行结果`);

  // —— 行数据
  after(cursor, () => onEvent({ event: "rows", data: scenario.rows }));
  cursor += 60;

  // —— 图表
  node("chart", 220, 80, "推荐图表");
  after(cursor, () => onEvent({ event: "chart", data: { option: scenario.chart } }));
  cursor += 60;

  // —— 总结：开始流式 token
  after(cursor, () =>
    onEvent({ event: "node", data: { name: "summarize", status: "running" } }),
  );
  cursor += 80;

  const tokens = tokenize(scenario.answer);
  for (const t of tokens) {
    after(cursor, () => onEvent({ event: "token", data: { delta: t } }));
    cursor += tokenInterval;
  }

  after(cursor, () =>
    onEvent({ event: "node", data: { name: "summarize", status: "ok" } }),
  );
  cursor += 60;

  after(cursor, () => {
    onEvent({ event: "done", data: { message_id: "mock" } });
    onDone?.();
  });

  return {
    abort: () => {
      aborted = true;
      timers.forEach((t) => clearTimeout(t));
    },
  };
}
