import { create } from "zustand";
import type { ChartSpec, RowsPayload } from "@/types/chat";

interface ChartState {
  /** 当前可视化的最近一条 chart spec（来自最近的助手回复） */
  chart: ChartSpec | null;
  rows: RowsPayload | null;
  sql: string | null;
  setChart: (spec: ChartSpec | null) => void;
  setRows: (rows: RowsPayload | null) => void;
  setSql: (sql: string | null) => void;
  reset: () => void;
}

export const useChartStore = create<ChartState>((set) => ({
  chart: null,
  rows: null,
  sql: null,
  setChart: (chart) => set({ chart }),
  setRows: (rows) => set({ rows }),
  setSql: (sql) => set({ sql }),
  reset: () => set({ chart: null, rows: null, sql: null }),
}));
