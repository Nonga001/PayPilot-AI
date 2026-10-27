"use client";

import {
  AllCommunityModule,
  ModuleRegistry,
  themeQuartz,
  type ColDef,
  type GridApi,
  type ICellRendererParams,
  type RowClickedEvent,
} from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { CircleCheck, CircleX, ExternalLink } from "lucide-react";
import type { Invoice, Transaction } from "@/lib/api";
import { RAIL_LABEL, dateTime, money, statusInfo } from "@/lib/format";

ModuleRegistry.registerModules([AllCommunityModule]);

export const ledgerTheme = themeQuartz.withParams({
  accentColor: "#0a8fb0",
  backgroundColor: "#ffffff",
  foregroundColor: "#142033",
  borderColor: "#d5dde7",
  chromeBackgroundColor: "#f5f7fa",
  headerTextColor: "#5b6b80",
  headerFontWeight: 600,
  oddRowBackgroundColor: "#fbfcfd",
  fontFamily: "var(--font-body), ui-sans-serif, system-ui, sans-serif",
  fontSize: 14,
  headerFontSize: 13,
  spacing: 7,
  wrapperBorderRadius: 16,
  browserColorScheme: "light",
});

const TONE: Record<string, string> = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  muted: "bg-cloud text-muted",
};

function StatusPill({ value }: { value: string }) {
  const s = statusInfo(value);
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TONE[s.tone]}`}>{s.label}</span>;
}

function Verified({ value }: ICellRendererParams<Transaction, boolean>) {
  return value ? (
    <CircleCheck className="mt-2.5 size-4 text-ok" aria-label="Amount verified" />
  ) : (
    <CircleX className="mt-2.5 size-4 text-bad" aria-label="Amount mismatch" />
  );
}

const amountCol = <T extends { amount: string; currency: string }>(): ColDef<T> => ({
  headerName: "Amount",
  valueGetter: (p) => (p.data ? Number(p.data.amount) : null),
  valueFormatter: (p) => (p.data ? money(p.data.amount, p.data.currency) : ""),
  type: "rightAligned",
  filter: "agNumberColumnFilter",
  width: 115,
  cellClass: "tabular font-semibold",
});

const PAYMENT_COLS: ColDef<Transaction>[] = [
  { field: "created_at", headerName: "Date", sort: "desc", valueFormatter: (p) => (p.value ? shortDate(p.value) : ""), tooltipValueGetter: (p) => (p.value ? dateTime(p.value) : ""), width: 150, minWidth: 140, filter: "agDateColumnFilter", filterValueGetter: (p) => (p.data ? new Date(p.data.created_at) : null) },
  { field: "receipt_number", headerName: "Receipt", width: 175, minWidth: 170, cellClass: "font-mono text-[13px]" },
  { field: "recipient", headerName: "Paid to", flex: 1, minWidth: 130 },
  { field: "invoice_number", headerName: "Invoice", width: 105 },
  amountCol<Transaction>(),
  { field: "currency", headerName: "Cur.", width: 75 },
  { field: "rail", headerName: "PayPal", width: 110, valueFormatter: (p) => SHORT_RAIL[p.value as string] ?? p.value ?? "", tooltipValueGetter: (p) => RAIL_LABEL[p.value as string] ?? "" },
  { field: "status", headerName: "Status", width: 135, cellRenderer: (p: ICellRendererParams<Transaction, string>) => <StatusPill value={p.value ?? ""} /> },
  { field: "decision", headerName: "Checks", width: 100, valueFormatter: (p) => ({ approved: "Cleared", review: "Reviewed", blocked: "Blocked" })[p.value as string] ?? "" },
  { field: "amount_verified", headerName: "Verified", width: 92, cellRenderer: Verified, filter: false },
];

const INVOICE_COLS: ColDef<Invoice>[] = [
  { field: "created_at", headerName: "Sent", sort: "desc", valueFormatter: (p) => (p.value ? shortDate(p.value) : ""), width: 150, minWidth: 140 },
  { field: "invoice_number", headerName: "Number", width: 120, cellClass: "font-mono text-[13px]" },
  { field: "recipient", headerName: "Client", flex: 1, minWidth: 150 },
  { field: "recipient_email", headerName: "Email", flex: 1, minWidth: 190 },
  amountCol<Invoice>(),
  { field: "currency", headerName: "Cur.", width: 85 },
  { field: "status", headerName: "Status", width: 140, cellRenderer: (p: ICellRendererParams<Invoice, string>) => <StatusPill value={p.value ?? ""} /> },
  {
    field: "payer_view_url",
    headerName: "",
    width: 70,
    sortable: false,
    filter: false,
    cellRenderer: (p: ICellRendererParams<Invoice, string>) =>
      p.value ? (
        <a href={p.value} target="_blank" rel="noreferrer" className="mt-2.5 inline-block text-ai" aria-label="Open invoice on PayPal">
          <ExternalLink className="size-4" />
        </a>
      ) : null,
  },
];

const DEFAULT_COL: ColDef = { sortable: true, filter: true, resizable: true, minWidth: 80 };

const shortDate = (iso: string) =>
  new Date(iso).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
const SHORT_RAIL: Record<string, string> = { payout: "Payouts", checkout: "Checkout", invoice: "Invoicing" };

type Props = { quickFilter: string; onApi: (api: GridApi) => void } & (
  | { kind: "payments"; rows: Transaction[]; onOpen: (t: Transaction) => void }
  | { kind: "invoices"; rows: Invoice[]; onOpen?: never }
);

export function LedgerGrid(props: Props) {
  const common = {
    theme: ledgerTheme,
    defaultColDef: DEFAULT_COL,
    quickFilterText: props.quickFilter,
    pagination: true,
    paginationPageSize: 20,
    paginationPageSizeSelector: [20, 50, 100],
    domLayout: "autoHeight" as const,
    autoSizeStrategy: { type: "fitGridWidth" as const },
    tooltipShowDelay: 300,
    animateRows: true,
    overlayNoRowsTemplate: "<span>Nothing here yet.</span>",
    onGridReady: (e: { api: GridApi }) => props.onApi(e.api),
  };
  if (props.kind === "payments") {
    return (
      <AgGridReact<Transaction>
        {...common}
        rowData={props.rows}
        columnDefs={PAYMENT_COLS}
        getRowId={(p) => p.data.id}
        rowClass="cursor-pointer"
        onRowClicked={(e: RowClickedEvent<Transaction>) => e.data && props.onOpen(e.data)}
      />
    );
  }
  return (
    <AgGridReact<Invoice>
      {...common}
      rowData={props.rows}
      columnDefs={INVOICE_COLS}
      getRowId={(p) => p.data.id}
    />
  );
}
