// The built-in Insights report, as AG Studio report state. Field ids ("requests.is_blocked") refer to
// the data sources in ./data.ts; "paypilot-*" widgets are PayPilot's own (./widgets.tsx).

import type { AgReportState, AgWidgetLayoutState } from "ag-studio";

// Canvas grid position, in tracks: 24 columns wide, rows of studioCanvasRowHeight.
const at = (xTrack: number, yTrack: number, xSpan: number, ySpan: number): AgWidgetLayoutState => ({ xTrack, yTrack, xSpan, ySpan });
const title = (text: string) => ({ title: { enabled: true, text } });
const sum = (id: string) => ({ id, aggregation: "sum" as const });
const avg = (id: string) => ({ id, aggregation: "avg" as const });
const countd = (id: string) => ({ id, aggregation: "countd" as const });

const FONT = "var(--font-body), ui-sans-serif, system-ui, sans-serif";
const type = (fontSize: number, fontWeight: "normal" | "bold" = "normal") => ({
  fontFamily: FONT,
  fontSize,
  fontWeight,
  fontStyle: "normal" as const,
});

const kpi = (text: string, value: { id: string; aggregation?: "sum" | "avg" | "countd" }, sparklineX?: string) => ({
  type: "value" as const,
  dataMapping: { value: [value], ...(sparklineX && { sparklineX: [{ id: sparklineX }] }) },
  format: {
    title: { enabled: true, text, typography: type(13, "bold") },
    caption: { enabled: true, text: "", typography: type(0) },
    style: { typography: type(24) },
  },
});

const sourceFilter = {
  type: "button-filter" as const,
  dataMapping: { value: [{ id: "requests.source" }] },
  format: { ...title("Data"), style: { selection: { type: "multiple" as const } } },
};

// PayPilot's own widget types aren't in Studio's default registry, so pages are typed loosely here.
const safety = {
  id: "safety",
  widgets: {
    "request-date": {
      type: "date-filter",
      dataMapping: { value: [{ id: "requests.date" }] },
      format: { style: { filterType: "relative" } },
    },
    source: sourceFilter,
    "kpi-requests": kpi("Requests handled", sum("requests.count"), "calendar::week"),
    "kpi-blocked": kpi("Blocked by rules", sum("requests.is_blocked"), "calendar::week"),
    "kpi-stopped": kpi("Money stopped", sum("requests.stopped_amount"), "calendar::week"),
    "kpi-paid-rate": kpi("Ended in a payment", { id: "paidRate" }),
    funnel: {
      type: "paypilot-safety-funnel",
      dataMapping: {},
      format: title("From request to PayPal"),
    },
    audit: {
      type: "paypilot-audit-chain",
      dataMapping: {},
      format: title("Audit trail"),
    },
    "decisions-by-week": {
      type: "column-chart-stacked",
      dataMapping: {
        categoryKey: [{ id: "calendar::week" }],
        valueKey: [sum("requests.count")],
        legendKey: [{ id: "requests.decision" }],
      },
      format: { ...title("What the rules decided, by week"), style: { theme: { common: { legend: { enabled: true } } } } },
    },
    "checks-fired": {
      type: "bar-chart-grouped",
      dataMapping: {
        categoryKey: [{ id: "checks.check" }],
        valueKey: [countd("checks.id")],
      },
      sort: [{ field: countd("checks.id"), direction: "desc" }],
      format: title("Checks that stopped or flagged a request"),
    },
    rails: {
      type: "donut-chart",
      dataMapping: { categoryKey: [{ id: "requests.rail" }], valueKey: [sum("requests.count")] },
      format: { ...title("PayPal rail chosen"), style: { custom: { pieDataLabel: { enabled: true }, totalLabel: { enabled: false } } } },
    },
    recent: {
      type: "grid",
      dataMapping: {
        cols: [
          { id: "requests.date" },
          { id: "requests.recipient" },
          { id: "requests.decision" },
          { id: "requests.outcome" },
          { id: "requests.currency" },
          sum("requests.amount"),
          sum("requests.risk_score"),
          { id: "requests.source" },
        ],
      },
      sort: [{ field: { id: "requests.date" }, direction: "desc" }],
      format: title("Requests"),
    },
  },
  widgetLayout: {
    "request-date": at(0, 0, 12, 8),
    source: at(12, 0, 12, 8),
    "kpi-requests": at(0, 8, 6, 7),
    "kpi-blocked": at(6, 8, 6, 7),
    "kpi-stopped": at(12, 8, 6, 7),
    "kpi-paid-rate": at(18, 8, 6, 7),
    funnel: at(0, 15, 16, 16),
    audit: at(16, 15, 8, 16),
    "decisions-by-week": at(0, 31, 14, 20),
    "checks-fired": at(14, 31, 10, 20),
    rails: at(0, 51, 8, 20),
    recent: at(8, 51, 16, 20),
  },
};

const payments = {
  id: "payments",
  widgets: {
    "payment-date": {
      type: "date-filter",
      dataMapping: { value: [{ id: "payments.date" }] },
      format: { style: { filterType: "relative" } },
    },
    currency: {
      type: "button-filter",
      dataMapping: { value: [{ id: "payments.currency" }] },
      format: { ...title("Currency"), style: { selection: { type: "single" } } },
    },
    "kpi-paid": kpi("Paid out", sum("payments.amount"), "calendar::week"),
    "kpi-count": kpi("Payments", countd("payments.id"), "calendar::week"),
    "kpi-fees": kpi("PayPal fees", sum("payments.fee")),
    "kpi-avg": kpi("Average payment", avg("payments.amount")),
    "paid-by-week": {
      type: "column-chart-stacked",
      dataMapping: {
        categoryKey: [{ id: "calendar::week" }],
        valueKey: [sum("payments.amount")],
        legendKey: [{ id: "payments.rail" }],
      },
      format: { ...title("Paid out by week and PayPal rail"), style: { theme: { common: { legend: { enabled: true } } } } },
    },
    "by-supplier": {
      type: "bar-chart-grouped",
      dataMapping: { categoryKey: [{ id: "payments.recipient" }], valueKey: [sum("payments.amount")] },
      sort: [{ field: sum("payments.amount"), direction: "desc" }],
      format: title("Paid to"),
    },
    ledger: {
      type: "grid",
      dataMapping: {
        cols: [
          { id: "payments.date" },
          { id: "payments.recipient" },
          { id: "payments.invoice_number" },
          { id: "payments.rail" },
          { id: "payments.status" },
          { id: "payments.currency" },
          sum("payments.amount"),
          sum("payments.fee"),
        ],
      },
      sort: [{ field: { id: "payments.date" }, direction: "desc" }],
      format: title("Payments"),
    },
  },
  // Money isn't converted between currencies, so this page starts on USD (the currency switch changes it).
  filter: {
    page: [{ field: { id: "payments.currency" }, model: { operator: "isIn", value: ["USD"] }, filterWidgetId: "currency" }],
  },
  widgetLayout: {
    "payment-date": at(0, 0, 12, 8),
    currency: at(12, 0, 12, 8),
    "kpi-paid": at(0, 8, 6, 7),
    "kpi-count": at(6, 8, 6, 7),
    "kpi-fees": at(12, 8, 6, 7),
    "kpi-avg": at(18, 8, 6, 7),
    "paid-by-week": at(0, 15, 14, 20),
    "by-supplier": at(14, 15, 10, 20),
    ledger: at(0, 35, 24, 24),
  },
};

const agent = {
  id: "agent",
  widgets: {
    source: sourceFilter,
    "kpi-latency": kpi("Average AI time (ms)", avg("requests.ai_latency_ms"), "calendar::week"),
    "kpi-review": kpi("Sent to a human", { id: "reviewRate" }),
    "kpi-block": kpi("Blocked", { id: "blockRate" }),
    "latency-by-week": {
      type: "line-chart",
      dataMapping: { categoryKey: [{ id: "calendar::week" }], valueKey: [avg("requests.ai_latency_ms")] },
      format: title("Average AI time per request, by week (ms)"),
    },
    "request-types": {
      type: "donut-chart",
      dataMapping: { categoryKey: [{ id: "requests.kind" }], valueKey: [sum("requests.count")] },
      format: { ...title("What owners asked for"), style: { custom: { pieDataLabel: { enabled: true }, totalLabel: { enabled: false } } } },
    },
    outcomes: {
      type: "pivot-grid",
      dataMapping: {
        rows: [{ id: "requests.decision" }],
        columns: [{ id: "requests.outcome" }],
        values: [sum("requests.count")],
      },
      format: title("Decision vs what happened next"),
    },
  },
  widgetLayout: {
    source: at(0, 0, 24, 8),
    "kpi-latency": at(0, 8, 8, 7),
    "kpi-review": at(8, 8, 8, 7),
    "kpi-block": at(16, 8, 8, 7),
    "latency-by-week": at(0, 15, 14, 20),
    "request-types": at(14, 15, 10, 20),
    outcomes: at(0, 35, 24, 16),
  },
};

export const PAGE_TITLES: Record<string, string> = { safety: "Safety", payments: "Payments", agent: "Agent" };

export const insightsReport = {
  selectedPageId: safety.id,
  // Filters live on the canvas (date, data source, currency); the side panel starts closed.
  panels: { filters: { collapsed: true } },
  pages: [safety, payments, agent],
} as unknown as AgReportState;
