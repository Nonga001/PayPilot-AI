"use client";

import { ArrowLeft, BadgeCheck, CircleCheckBig, Printer, TriangleAlert } from "lucide-react";
import Link from "next/link";
import type { ReceiptData } from "@/lib/api";
import { dateTime, eventLabel, money, shortHash } from "@/lib/format";
import { Logo } from "./ui";

function Row({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-6 py-2">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className={`min-w-0 break-all text-right text-[15px] ${mono ? "font-mono text-[13px]" : ""}`}>{value || "—"}</dd>
    </div>
  );
}

export function Receipt({ data, fresh = false }: { data: ReceiptData; fresh?: boolean }) {
  const t = data.transaction;
  const approval = data.audit.find((e) => e.event === "human.approved");
  const acknowledged = Boolean(approval?.data?.acknowledged_risks);

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="no-print mb-5 flex items-center justify-between">
        <Link href="/" className="inline-flex items-center gap-1.5 text-sm font-medium text-muted hover:text-ink">
          <ArrowLeft className="size-4" aria-hidden />
          Back to PayPilot
        </Link>
        <button
          type="button"
          onClick={() => window.print()}
          className="inline-flex items-center gap-2 rounded-xl bg-panel px-3.5 py-2 text-sm font-semibold ring-1 ring-line hover:ring-faint"
        >
          <Printer className="size-4" aria-hidden />
          Print or save PDF
        </button>
      </div>

      <article className="print-flat rounded-3xl bg-panel p-6 shadow-[0_1px_2px_rgba(20,32,51,0.06),0_12px_32px_-12px_rgba(20,32,51,0.18)] ring-1 ring-line sm:p-10">
        <header className="flex items-start justify-between gap-4">
          <Logo />
          <div className="text-right">
            <div className="text-sm text-muted">Receipt</div>
            <div className="font-mono text-sm">{t.receipt_number}</div>
          </div>
        </header>

        <div className="mt-10">
          {fresh && (
            <p className="mb-2 flex items-center gap-2 text-sm font-medium text-ok">
              <CircleCheckBig className="size-4" aria-hidden />
              Payment complete
            </p>
          )}
          <div className="font-display tabular text-5xl font-semibold tracking-tight">{money(t.amount, t.currency)}</div>
          <p className="mt-2 text-[15px] text-muted">
            Paid to <span className="font-medium text-ink">{t.recipient || t.recipient_email}</span> on {dateTime(t.created_at)}
          </p>
          {!t.amount_verified && (
            <p className="mt-4 flex items-start gap-2 rounded-xl bg-bad-soft p-3 text-sm text-bad">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              PayPal captured a different amount than the one you approved ({data.proposal?.payment.amount}{" "}
              {data.proposal?.payment.currency}). This has been flagged in the audit trail.
            </p>
          )}
        </div>

        <dl className="mt-8 divide-y divide-line border-y border-line">
          <Row label="Purpose" value={t.description} />
          <Row label="Invoice" value={t.invoice_number} />
          <Row label="Status" value={t.status === "COMPLETED" ? "Completed" : t.status} />
          <Row label="Paid from" value={[t.payer_name, t.payer_email].filter(Boolean).join(", ")} />
          {t.paypal_fee && <Row label="PayPal fee" value={money(t.paypal_fee, t.currency)} />}
          {t.net_amount && <Row label="Net to recipient" value={money(t.net_amount, t.currency)} />}
          <Row label="Approved by" value={acknowledged ? "You, after reviewing flagged details" : "You, all checks passed"} />
          <Row label="PayPal order" value={t.order_id} mono />
          <Row label="PayPal capture" value={t.capture_id} mono />
        </dl>

        {data.proposal && (
          <section className="mt-8">
            <h2 className="text-sm text-muted">Original instruction</h2>
            <blockquote className="mt-1.5 border-l-2 border-ai pl-3 text-[15px] italic text-ink">
              {data.proposal.message}
            </blockquote>
          </section>
        )}

        <section className="mt-8">
          <h2 className="flex items-center gap-2 font-display text-base font-semibold">
            <BadgeCheck className="size-4 text-ok" aria-hidden />
            Audit trail
          </h2>
          <ol className="mt-3 space-y-0">
            {data.audit.map((e, i) => (
              <li key={e.seq} className="grid grid-cols-[1rem_1fr_auto] gap-3">
                <span className="flex flex-col items-center" aria-hidden>
                  <span className="mt-1.5 size-2 rounded-full bg-ink" />
                  {i < data.audit.length - 1 && <span className="w-px flex-1 bg-line" />}
                </span>
                <div className="pb-3">
                  <div className="text-[15px]">{eventLabel(e.event)}</div>
                  <div className="text-xs text-faint">{dateTime(e.ts)}</div>
                </div>
                <code className="pt-0.5 font-mono text-xs text-faint" title={e.hash}>
                  {shortHash(e.hash, 12)}
                </code>
              </li>
            ))}
          </ol>
        </section>

        <footer className="mt-8 border-t border-line pt-5 text-xs leading-relaxed text-faint">
          PayPal Sandbox transaction. Each audit hash includes the hash before it, so this record can&apos;t be edited without
          detection. Final hash: <code className="break-all font-mono">{t.audit_hash}</code>
        </footer>
      </article>
    </div>
  );
}
