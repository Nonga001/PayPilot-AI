import { ArrowLeft, ExternalLink, MailCheck } from "lucide-react";
import type { Invoice } from "@/lib/api";
import { money, statusInfo } from "@/lib/format";

export function InvoiceSent({ invoice, onDone }: { invoice: Invoice; onDone: () => void }) {
  const st = statusInfo(invoice.status);
  return (
    <section className="rounded-2xl bg-ok-soft p-6" aria-live="polite">
      <p className="flex items-center gap-2 text-sm font-medium text-ok">
        <MailCheck className="size-4" aria-hidden />
        Invoice sent through PayPal
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
          <dd>{st.label}</dd>
        </div>
        <div>
          <dt className="text-faint">PayPal ID</dt>
          <dd className="truncate font-mono">{invoice.paypal_invoice_id}</dd>
        </div>
      </dl>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        {invoice.payer_view_url && (
          <a
            href={invoice.payer_view_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#22324d]"
          >
            <ExternalLink className="size-4" aria-hidden />
            Open what your client sees
          </a>
        )}
        <button type="button" onClick={onDone} className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden />
          Start something new
        </button>
      </div>
      <p className="mt-4 text-xs text-muted">Ask PayPilot &ldquo;Has {invoice.recipient || "this client"} paid?&rdquo; any time to check PayPal for the status.</p>
    </section>
  );
}
