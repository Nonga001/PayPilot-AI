"use client";

import type { GridApi } from "ag-grid-community";
import { Download, FileText, Loader2, ReceiptText, Search } from "lucide-react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Shell } from "@/components/shell";
import { api, type Invoice, type Transaction } from "@/lib/api";
import { money } from "@/lib/format";

// The grid is the heaviest bundle in the app; load it only on this page, only in the browser.
const LedgerGrid = dynamic(() => import("@/components/ledger-grid").then((m) => m.LedgerGrid), {
  ssr: false,
  loading: () => (
    <div className="grid h-64 place-items-center rounded-2xl bg-panel ring-1 ring-line">
      <Loader2 className="size-6 animate-spin text-ai" aria-label="Loading ledger" />
    </div>
  ),
});

type Tab = "payments" | "invoices";

export default function LedgerPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("payments");
  const [txs, setTxs] = useState<Transaction[] | null>(null);
  const [invs, setInvs] = useState<Invoice[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const grid = useRef<GridApi | null>(null);

  useEffect(() => {
    Promise.all([api.transactions(), api.invoices()])
      .then(([t, i]) => {
        setTxs(t.transactions);
        setInvs(i.invoices);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const totals = useMemo(() => {
    const out: Record<string, number> = {};
    for (const t of txs ?? []) out[t.currency] = (out[t.currency] ?? 0) + Number(t.amount);
    return Object.entries(out);
  }, [txs]);

  const outstanding = useMemo(() => {
    const out: Record<string, number> = {};
    for (const i of invs ?? [])
      if (["SENT", "UNPAID", "PARTIALLY_PAID", "SCHEDULED"].includes(i.status))
        out[i.currency] = (out[i.currency] ?? 0) + Number(i.amount);
    return Object.entries(out);
  }, [invs]);

  function exportCsv() {
    grid.current?.exportDataAsCsv({ fileName: `paypilot-${tab}-${new Date().toISOString().slice(0, 10)}.csv` });
  }

  return (
    <Shell>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold tracking-tight">Ledger</h1>
          <p className="mt-1 text-[15px] text-muted">
            {txs === null
              ? "Loading…"
              : `${txs.length} ${txs.length === 1 ? "payment" : "payments"}${totals.length ? `, ${totals.map(([c, v]) => money(v, c)).join(" + ")} paid out` : ""}${
                  outstanding.length ? `. ${outstanding.map(([c, v]) => money(v, c)).join(" + ")} invoiced and unpaid` : ""
                }.`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative">
            <span className="sr-only">Search the ledger</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" aria-hidden />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search names, invoices, amounts"
              className="w-64 rounded-xl bg-panel py-2 pl-9 pr-3 text-sm ring-1 ring-line placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-ai"
            />
          </label>
          <button
            type="button"
            onClick={exportCsv}
            className="inline-flex items-center gap-2 rounded-xl bg-ink px-3.5 py-2 text-sm font-semibold text-white hover:bg-[#22324d]"
          >
            <Download className="size-4" aria-hidden />
            Export CSV
          </button>
        </div>
      </div>

      <div role="tablist" aria-label="Ledger view" className="mt-6 flex gap-1 border-b border-line">
        {(
          [
            ["payments", "Payments out", ReceiptText, txs?.length],
            ["invoices", "Invoices sent", FileText, invs?.length],
          ] as const
        ).map(([key, label, Icon, n]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-medium ${
              tab === key ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            <Icon className="size-4" aria-hidden />
            {label}
            {n !== undefined && <span className="rounded-full bg-cloud px-1.5 text-xs tabular text-muted">{n}</span>}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {error ? (
          <p className="rounded-xl bg-bad-soft p-4 text-sm text-bad">{error}</p>
        ) : tab === "payments" ? (
          txs && (
            <LedgerGrid
              onApi={(a) => (grid.current = a)}
              kind="payments"
              rows={txs}
              quickFilter={q}
              onOpen={(t) => router.push(`/receipt?id=${encodeURIComponent(t.receipt_number)}`)}
            />
          )
        ) : (
          invs && <LedgerGrid onApi={(a) => (grid.current = a)} kind="invoices" rows={invs} quickFilter={q} />
        )}
      </div>
      <p className="mt-3 text-xs text-faint">Click a payment to open its receipt and audit trail. Filters are in each column header.</p>
    </Shell>
  );
}
