"use client";

import { ArrowLeft, Check, CircleCheck, Copy, ExternalLink, KeyRound, Loader2, MailCheck, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { api, type Invoice } from "@/lib/api";
import { money, statusInfo } from "@/lib/format";

const OPEN = ["SENT", "UNPAID", "PARTIALLY_PAID", "SCHEDULED"];
const POLL_MS = 8000;
const POLL_FOR_MS = 10 * 60 * 1000;

export function InvoiceSent({
  invoice: first,
  onDone,
  demoPayer,
}: {
  invoice: Invoice;
  onDone: () => void;
  demoPayer: { email: string; password: string } | null;
}) {
  const [invoice, setInvoice] = useState(first);
  const [checking, setChecking] = useState(false);
  const open = OPEN.includes(invoice.status.toUpperCase());
  const paid = invoice.status.toUpperCase() === "PAID" || invoice.status.toUpperCase() === "MARKED_AS_PAID";
  const st = statusInfo(invoice.status);
  const [simulatedPaid, setSimulatedPaid] = useState(false);

  // While the invoice is open, ask PayPal every few seconds whether the client has paid.
  useEffect(() => {
    if (!open) return;
    const started = Date.now();
    const t = setInterval(() => {
      if (Date.now() - started > POLL_FOR_MS) return clearInterval(t);
      api.refresh(invoice.id).then((r) => r.invoice && setInvoice(r.invoice)).catch(() => {});
    }, POLL_MS);
    return () => clearInterval(t);
  }, [open, invoice.id]);

  const [simulating, setSimulating] = useState(false);
  const [simError, setSimError] = useState<string | null>(null);
  const simulate = () => {
    setSimulating(true);
    setSimError(null);
    api
      .simulateInvoicePayment(invoice.id)
      .then((r) => {
        setSimulatedPaid(true);
        setInvoice(r.invoice);
      })
      .catch((e: Error) => setSimError(e.message))
      .finally(() => setSimulating(false));
  };

  const checkNow = () => {
    setChecking(true);
    api
      .refresh(invoice.id)
      .then((r) => r.invoice && setInvoice(r.invoice))
      .catch(() => {})
      .finally(() => setChecking(false));
  };

  const isDemoClient = demoPayer && demoPayer.email.toLowerCase() === invoice.recipient_email.toLowerCase();

  return (
    <section className="rounded-2xl bg-ok-soft p-6" aria-live="polite">
      <p className="flex items-center gap-2 text-sm font-medium text-ok">
        {paid ? <CircleCheck className="size-4" aria-hidden /> : <MailCheck className="size-4" aria-hidden />}
        {paid ? (simulatedPaid ? "Paid (simulated client payment)" : "Paid by your client through PayPal") : "Invoice sent through PayPal"}
      </p>
      <div className="mt-3 font-display tabular text-4xl font-semibold tracking-tight">{money(invoice.amount, invoice.currency)}</div>
      <p className="mt-1 text-[15px] text-muted">
        Requested from <span className="font-medium text-ink">{invoice.recipient || invoice.recipient_email}</span> at{" "}
        {invoice.recipient_email}
      </p>
      <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-faint">Invoice number</dt>
          <dd className="font-mono">{invoice.invoice_number || "—"}</dd>
        </div>
        <div>
          <dt className="text-faint">Status</dt>
          <dd className="flex items-center gap-1.5">
            <span className={paid ? "font-semibold text-ok" : ""}>{st.label}</span>
            {open && <Loader2 className="size-3.5 animate-spin text-faint" aria-label="Watching PayPal for payment" />}
          </dd>
        </div>
        <div>
          <dt className="text-faint">PayPal ID</dt>
          <dd className="truncate font-mono">{invoice.paypal_invoice_id}</dd>
        </div>
      </dl>

      {open && (
        <div className="mt-5 rounded-xl bg-panel p-4 text-sm ring-1 ring-line">
          <p className="flex items-center gap-2 font-semibold text-ink">
            <KeyRound className="size-4 text-ai" aria-hidden />
            Now pay it as the client (PayPal sandbox)
          </p>
          <p className="mt-1 text-muted">
            Open the invoice, log in{isDemoClient ? " with the details below" : " with that client's sandbox account"}, and
            pay. PayPilot will see it and mark the invoice Paid.
          </p>
          {isDemoClient && (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              <CopyField label="Email" value={demoPayer.email} />
              <CopyField label="Password" value={demoPayer.password} />
            </div>
          )}
          {invoice.payer_view_url && (
            <a
              href={invoice.payer_view_url}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#22324d]"
            >
              <ExternalLink className="size-4" aria-hidden />
              Open what your client sees
            </a>
          )}
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        {open && (
          <button
            type="button"
            onClick={checkNow}
            disabled={checking}
            className="inline-flex items-center gap-2 rounded-xl bg-panel px-3.5 py-2.5 text-sm font-medium text-ink ring-1 ring-line hover:ring-faint disabled:opacity-60"
          >
            <RefreshCw className={`size-4 ${checking ? "animate-spin" : ""}`} aria-hidden />
            Check payment now
          </button>
        )}
        <button type="button" onClick={onDone} className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden />
          Start something new
        </button>
      </div>
      {open && (
        <p className="mt-4 text-xs text-muted">
          Short on time?{" "}
          <button
            type="button"
            onClick={simulate}
            disabled={simulating}
            className="inline-flex items-center gap-1 font-medium text-ai underline-offset-2 hover:underline disabled:opacity-60"
            title="Records a bank-transfer payment on the invoice in PayPal. Sandbox only; marked as simulated in the audit trail."
          >
            {simulating && <Loader2 className="size-3 animate-spin" aria-hidden />}
            {simulating ? "Recording payment…" : "Simulate the client paying"}
          </button>
          {simError && <span className="ml-2 text-bad">{simError}</span>}
        </p>
      )}
      <p className="mt-2 text-xs text-muted">
        {open
          ? "PayPilot is watching PayPal and will update this the moment the client pays. The ledger updates too."
          : `The ledger shows this invoice as ${st.label.toLowerCase()}.`}
      </p>
    </section>
  );
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [done, setDone] = useState(false);
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-lg bg-cloud px-3 py-2">
      <span className="shrink-0 text-xs text-faint">{label}</span>
      <code className="min-w-0 flex-1 truncate font-mono text-[13px] text-ink">{value}</code>
      <button
        type="button"
        onClick={() => {
          navigator.clipboard?.writeText(value).then(() => {
            setDone(true);
            setTimeout(() => setDone(false), 1500);
          });
        }}
        className="shrink-0 rounded-md p-1 text-muted hover:bg-panel hover:text-ink"
        aria-label={`Copy ${label.toLowerCase()}`}
      >
        {done ? <Check className="size-4 text-ok" /> : <Copy className="size-4" />}
      </button>
    </div>
  );
}
