import { useMemo, useState } from "react";
import {
  Button,
  Empty,
  Space,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import {
  AreaChartOutlined,
  CopyOutlined,
  DatabaseOutlined,
  FullscreenOutlined,
  TableOutlined,
} from "@ant-design/icons";
import ReactECharts from "echarts-for-react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useChartStore } from "@/store/chartStore";
import type { ColumnsType } from "antd/es/table";
import type { ChartSpec, RowCell } from "@/types/chat";

const { Text } = Typography;

export default function ChartPanel(): JSX.Element {
  const chart = useChartStore((s) => s.chart);
  const rows = useChartStore((s) => s.rows);
  const sql = useChartStore((s) => s.sql);
  const [tab, setTab] = useState<"chart" | "table" | "sql">("chart");
  const [fullscreen, setFullscreen] = useState(false);
  const chartOption = useMemo(() => (chart ? normalizeChartOption(chart) : null), [chart]);

  const tableColumns: ColumnsType<Record<string, RowCell>> = useMemo(() => {
    if (!rows) return [];
    return rows.columns.map((c) => ({
      title: c,
      dataIndex: c,
      key: c,
      ellipsis: true,
      render: (v: RowCell) => formatCell(v),
    }));
  }, [rows]);

  /** 后端 rows.data 为对象数组；列顺序由 columns 决定 */
  const tableData = useMemo(() => {
    if (!rows) return [];
    return rows.data.map((row, idx) => {
      const obj: Record<string, RowCell> = { key: idx };
      rows.columns.forEach((c) => {
        obj[c] = row[c] ?? null;
      });
      return obj;
    });
  }, [rows]);

  const isEmpty = !chart && !rows && !sql;

  const handleCopySql = async () => {
    if (!sql) return;
    try {
      await navigator.clipboard.writeText(sql);
      message.success("已复制 SQL");
    } catch {
      message.error("复制失败");
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        ...(fullscreen
          ? {
              position: "fixed",
              inset: 0,
              zIndex: 1000,
              background: "#fff",
              borderRadius: 0,
            }
          : {}),
      }}
    >
      <div
        style={{
          padding: "8px 16px",
          borderBottom: "1px solid #f1f3f7",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Space size={8}>
          <Text strong>可视化面板</Text>
          {rows && <Tag color="blue">{rows.data.length} 行</Tag>}
        </Space>
        <Space>
          {tab === "sql" && sql && (
            <Tooltip title="复制 SQL">
              <Button
                size="small"
                type="text"
                icon={<CopyOutlined />}
                onClick={handleCopySql}
              />
            </Tooltip>
          )}
          <Tooltip title={fullscreen ? "退出全屏" : "全屏查看"}>
            <Button
              size="small"
              type="text"
              icon={<FullscreenOutlined />}
              onClick={() => setFullscreen((v) => !v)}
            />
          </Tooltip>
        </Space>
      </div>

      <Tabs
        activeKey={tab}
        onChange={(k) => setTab(k as typeof tab)}
        size="small"
        style={{ paddingInline: 12, marginTop: 4 }}
        items={[
          {
            key: "chart",
            label: (
              <span>
                <AreaChartOutlined /> 图表
              </span>
            ),
          },
          {
            key: "table",
            label: (
              <span>
                <TableOutlined /> 数据表
              </span>
            ),
          },
          {
            key: "sql",
            label: (
              <span>
                <DatabaseOutlined /> SQL
              </span>
            ),
          },
        ]}
      />

      <div style={{ flex: 1, minHeight: 0, padding: 12, overflow: "hidden" }}>
        {isEmpty ? (
          <div style={{ height: "100%", display: "grid", placeItems: "center" }}>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="发起一次提问后，图表 / 数据表 / SQL 将显示在这里"
            />
          </div>
        ) : tab === "chart" ? (
          chartOption ? (
            <ReactECharts
              option={chartOption}
              style={{ height: "100%", width: "100%" }}
              notMerge
              lazyUpdate
            />
          ) : (
            <Empty description="暂无图表" />
          )
        ) : tab === "table" ? (
          rows ? (
            <Table
              size="small"
              columns={tableColumns}
              dataSource={tableData}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                pageSizeOptions: [10, 20, 50, 100],
                showTotal: (t) => `共 ${t} 行`,
              }}
              scroll={{ x: "max-content", y: 360 }}
            />
          ) : (
            <Empty description="暂无数据" />
          )
        ) : sql ? (
          <div
            style={{
              height: "100%",
              border: "1px solid #e5e7eb",
              borderRadius: 8,
              background: "#fafbfd",
              overflow: "auto",
            }}
          >
            <SyntaxHighlighter
              language="sql"
              style={oneLight}
              showLineNumbers
              customStyle={{
                margin: 0,
                padding: 16,
                background: "transparent",
                fontSize: 12.5,
              }}
              wrapLongLines
            >
              {sql}
            </SyntaxHighlighter>
          </div>
        ) : (
          <Empty description="暂无 SQL" />
        )}
      </div>
    </div>
  );
}

function formatCell(v: RowCell): string {
  if (v === null || v === undefined) return "-";
  if (typeof v === "number") {
    if (Math.abs(v) >= 1000) return v.toLocaleString();
    if (Number.isFinite(v) && !Number.isInteger(v)) return v.toFixed(3);
  }
  return String(v);
}

function normalizeChartOption(chart: ChartSpec): ChartSpec {
  const option = chart as Record<string, unknown>;
  const series = option.series;
  const firstSeries = Array.isArray(series) ? series[0] : series;
  const isPie =
    isRecord(firstSeries) && String(firstSeries.type ?? "").toLowerCase() === "pie";

  if (isPie) {
    return {
      ...option,
      title: normalizeTitle(option.title, "center"),
      legend: normalizeLegend(option.legend, { bottom: 4, type: "scroll" }),
      series: Array.isArray(series)
        ? series.map((item) =>
            isRecord(item)
              ? { center: ["50%", "54%"], radius: "60%", ...item }
              : item,
          )
        : series,
    } as ChartSpec;
  }

  return {
    ...option,
    title: normalizeTitle(option.title, "left"),
    legend: normalizeLegend(option.legend, {
      top: 64,
      left: "center",
      type: "scroll",
      itemGap: 20,
    }),
    grid: normalizeGrid(option.grid),
  } as ChartSpec;
}

function normalizeTitle(title: unknown, left: "left" | "center"): Record<string, unknown> {
  const raw = Array.isArray(title) ? title[0] : title;
  const obj = isRecord(raw) ? raw : {};
  return {
    ...obj,
    left: obj.left ?? left,
    top: obj.top ?? 0,
    itemGap: obj.itemGap ?? 8,
    textStyle: {
      fontSize: 16,
      fontWeight: 600,
      color: "#1f2937",
      ...(isRecord(obj.textStyle) ? obj.textStyle : {}),
    },
    subtextStyle: {
      fontSize: 12,
      color: "#6b7280",
      lineHeight: 18,
      ...(isRecord(obj.subtextStyle) ? obj.subtextStyle : {}),
    },
  };
}

function normalizeLegend(
  legend: unknown,
  defaults: Record<string, unknown>,
): Record<string, unknown> {
  const obj = isRecord(legend) ? legend : {};
  return { ...obj, ...defaults };
}

function normalizeGrid(grid: unknown): Record<string, unknown> {
  const obj = isRecord(grid) ? grid : {};
  return {
    ...obj,
    left: 48,
    right: 24,
    top: 120,
    bottom: 48,
    containLabel: true,
  };
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return Boolean(v) && typeof v === "object" && !Array.isArray(v);
}
