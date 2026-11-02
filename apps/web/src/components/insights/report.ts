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

// Each page answers one question with a few widgets. Switch to Edit (or ask the AI) to add more.
const safety = {
  id: "safety",
  widgets: {
    "kpi-requests": kpi("Requests handled", sum("requests.count")),
    "kpi-blocked": kpi("Blocked by rules", sum("requests.is_blocked")),
    "kpi-flagged": kpi("Sent to a human", sum("requests.is_flagged")),
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
    "checks-fired": {
      type: "bar-chart-grouped",
      dataMapping: { categoryKey: [{ id: "checks.check" }], valueKey: [countd("checks.id")] },
      sort: [{ field: countd("checks.id"), direction: "desc" }],
      format: title("Checks that stopped or flagged a request"),
    },
    recent: {
      type: "grid",
      dataMapping: {
        cols: [
          { id: "requests.date" },
          { id: "requests.recipient" },
          { id: "requests.decision" },
          { id: "requests.outcome" },
          { id: "requests.source" },
        ],
      },
      sort: [{ field: { id: "requests.date" }, direction: "desc" }],
      format: title("Requests"),
    },
  },
  widgetLayout: {
    "kpi-requests": at(0, 0, 6, 6),
    "kpi-blocked": at(6, 0, 6, 6),
    "kpi-flagged": at(12, 0, 6, 6),
    "kpi-paid-rate": at(18, 0, 6, 6),
    funnel: at(0, 6, 16, 16),
    audit: at(16, 6, 8, 16),
    "checks-fired": at(0, 22, 10, 18),
    recent: at(10, 22, 14, 18),
  },
};

const payments = {
  id: "payments",
  widgets: {
    currency: {
      type: "button-filter",
      dataMapping: { value: [{ id: "payments.currency" }] },
      format: { ...title("Currency"), style: { selection: { type: "single" } } },
    },
    "kpi-paid": kpi("Paid out", sum("payments.amount")),
    "kpi-count": kpi("Payments", countd("payments.id")),
    "kpi-fees": kpi("PayPal fees", sum("payments.fee")),
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
          sum("payments.amount"),
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
    "kpi-paid": at(0, 0, 6, 8),
    "kpi-count": at(6, 0, 6, 8),
    "kpi-fees": at(12, 0, 6, 8),
    currency: at(18, 0, 6, 8),
    "by-supplier": at(0, 8, 10, 18),
    ledger: at(10, 8, 14, 18),
  },
};

const agent = {
  id: "agent",
  widgets: {
    "kpi-latency": kpi("Average AI time (ms)", avg("requests.ai_latency_ms")),
    "kpi-review": kpi("Sent to a human", { id: "reviewRate" }),
    "kpi-block": kpi("Blocked", { id: "blockRate" }),
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
    "kpi-latency": at(0, 0, 8, 6),
    "kpi-review": at(8, 0, 8, 6),
    "kpi-block": at(16, 0, 8, 6),
    "request-types": at(0, 6, 9, 18),
    outcomes: at(9, 6, 15, 18),
  },
};

export const PAGE_TITLES: Record<string, string> = { safety: "Safety", payments: "Payments", agent: "Agent" };

export const insightsReport = {
  selectedPageId: safety.id,
  // The filters panel starts closed; Data and Currency switches sit on the canvas.
  panels: { filters: { collapsed: true } },
  pages: [safety, payments, agent],
} as unknown as AgReportState;
