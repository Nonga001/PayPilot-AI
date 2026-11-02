// AG Studio data sources for the Insights page: one table per row type the API returns
// (GET /insights), how they relate, a shared calendar and a few calculated measures.

import type {
  AgDataSourcesDefinition,
  AgExpressionFieldDefinition,
  AgFieldDefinition,
  AgFormat,
  AgRelationDefinition,
} from "ag-studio";
import type { InsightsData } from "@/lib/api";

const CALENDAR_ID = "calendar";

type FieldSpec = [id: string, name: string, format: AgFormat, hide?: boolean];

const fields = (specs: FieldSpec[]): AgFieldDefinition[] =>
  specs.map(([id, name, format, hide]) => ({ id, name, format, ...(hide && { hide }) }));

const manyToOne = (id: string, source: string, target: string): AgRelationDefinition => {
  const [sourceTable, sourceField] = source.split(".");
  const [targetTable, targetField] = target.split(".");
  return {
    id,
    source: { tableId: sourceTable, fieldId: sourceField },
    target: { tableId: targetTable, fieldId: targetField },
    type: "many-to-one",
  };
};

const onCalendar = (tableId: string, fieldId: string): AgRelationDefinition => ({
  id: `${tableId}-${fieldId}-calendar`,
  source: { tableId, fieldId },
  target: { calendarId: CALENDAR_ID },
});

const sumOf = (id: string) => ({ id, aggregation: "sum" as const });

const ratio = (id: string, name: string, description: string, numerator: string, denominator: string): AgExpressionFieldDefinition => ({
  id,
  name,
  description,
  format: "percentageFormat",
  isMeasure: true,
  expression: { operator: "divide", inputs: [sumOf(numerator), sumOf(denominator)] },
});

// Flags summed by the ratios below. Studio sums numbers, so each request carries 1/0 columns.
function withFlags(rows: InsightsData["tables"]["requests"]) {
  return rows.map((r) => ({
    ...r,
    count: 1,
    is_blocked: r.decision === "Blocked" ? 1 : 0,
    is_flagged: r.decision === "Review" ? 1 : 0,
    is_paid: r.outcome === "Paid" ? 1 : 0,
    stopped_amount: r.decision === "Blocked" && typeof r.amount === "number" ? r.amount : 0,
  }));
}

export function buildStudioData(d: InsightsData): AgDataSourcesDefinition {
  const requests = withFlags(d.tables.requests);
  const dates = d.tables.requests.map((r) => r.date as string).filter(Boolean).sort();
  const today = d.as_of.slice(0, 10);

  return {
    description:
      "PayPilot, an AI payment agent for a small business. Each request is something the owner typed: pay a supplier, " +
      "invoice a client, or a question. Deterministic rules then approve it, flag it for human review, or block it. " +
      "Amounts are in their own currency (USD, EUR, GBP) and are not converted, so filter by currency before summing money. " +
      'Rows with source "Sample" are a generated demo history; "Live" rows are real sandbox activity.',
    sources: [
      {
        id: "requests",
        description:
          "One row per request the agent handled. Decision is what the rules decided; outcome is what happened after (paid, cancelled, still waiting).",
        data: requests,
        fields: fields([
          ["id", "Request ID", "textFormat", true],
          ["date", "Request Date", "dateFormat"],
          ["created_at", "Requested At", "dateTimeFormat", true],
          ["kind", "Request Type", "textFormat"],
          ["rail", "PayPal Rail", "textFormat"],
          ["decision", "Decision", "textFormat"],
          ["outcome", "Outcome", "textFormat"],
          ["risk_level", "Risk Level", "textFormat"],
          ["risk_score", "Risk Score", "integerFormat"],
          ["amount", "Requested Amount", "currencyFormat"],
          ["currency", "Currency", "textFormat"],
          ["recipient", "Payee / Client", "textFormat"],
          ["ai_source", "Read By", "textFormat"],
          ["ai_latency_ms", "AI Time (ms)", "integerFormat"],
          ["checks_failed", "Checks Failed", "integerFormat"],
          ["count", "Requests", "integerFormat"],
          ["is_blocked", "Blocked", "integerFormat"],
          ["is_flagged", "Flagged For Review", "integerFormat"],
          ["is_paid", "Paid", "integerFormat"],
          ["stopped_amount", "Amount Stopped", "currencyFormat"],
          ["source", "Data Source", "textFormat"],
        ]),
      },
      {
        id: "checks",
        name: "Failed Checks",
        description: "One row per safety check that failed on a request. Severity says whether it blocked the request or asked for a human look.",
        data: d.tables.checks,
        fields: fields([
          ["id", "Check Row ID", "textFormat", true],
          ["request_id", "Request ID", "textFormat", true],
          ["check", "Check", "textFormat"],
          ["check_id", "Check Code", "textFormat", true],
          ["severity", "Severity", "textFormat"],
          ["date", "Check Date", "dateFormat"],
          ["source", "Check Data Source", "textFormat", true],
        ]),
      },
      {
        id: "payments",
        description: "Money that actually left through PayPal (Payouts or Checkout), after approval.",
        data: d.tables.payments,
        fields: fields([
          ["id", "Payment ID", "textFormat", true],
          ["request_id", "Request ID", "textFormat", true],
          ["date", "Payment Date", "dateFormat"],
          ["recipient", "Paid To", "textFormat"],
          ["rail", "Payment Rail", "textFormat"],
          ["status", "Payment Status", "textFormat"],
          ["amount", "Paid Amount", "currencyFormat"],
          ["currency", "Payment Currency", "textFormat"],
          ["fee", "PayPal Fee", "currencyFormat"],
          ["verified", "Amount Verified", "booleanFormat"],
          ["invoice_number", "Invoice Number", "textFormat"],
          ["source", "Payment Data Source", "textFormat", true],
        ]),
      },
      {
        id: "invoices",
        description: "PayPal invoices sent to clients.",
        data: d.tables.invoices,
        fields: fields([
          ["id", "Invoice ID", "textFormat", true],
          ["request_id", "Request ID", "textFormat", true],
          ["date", "Invoice Date", "dateFormat"],
          ["client", "Client", "textFormat"],
          ["status", "Invoice Status", "textFormat"],
          ["amount", "Invoice Amount", "currencyFormat"],
          ["currency", "Invoice Currency", "textFormat"],
          ["source", "Invoice Data Source", "textFormat", true],
        ]),
      },
    ],
    relationships: [
      manyToOne("check-request", "checks.request_id", "requests.id"),
      manyToOne("payment-request", "payments.request_id", "requests.id"),
      manyToOne("invoice-request", "invoices.request_id", "requests.id"),
      onCalendar("requests", "date"),
      onCalendar("payments", "date"),
      onCalendar("invoices", "date"),
    ],
    calendars: [
      {
        id: CALENDAR_ID,
        label: "Calendar",
        range: {
          from: { type: "date", value: dates[0] ?? today },
          to: { type: "date", value: today },
        },
        fragments: ["year", "quarter", "month", "week", "day", "dayOfWeek"],
      },
    ],
    expressions: [
      ratio("blockRate", "Block Rate", "Share of requests the rules blocked.", "requests.is_blocked", "requests.count"),
      ratio("reviewRate", "Review Rate", "Share of requests flagged for a human check.", "requests.is_flagged", "requests.count"),
      ratio("paidRate", "Paid Rate", "Share of requests that ended in a PayPal payment.", "requests.is_paid", "requests.count"),
    ],
  };
}
