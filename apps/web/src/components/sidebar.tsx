import { ChevronRight, Link2, Link2Off, ReceiptText, Wallet } from "lucide-react";
import Link from "next/link";
import type { Dashboard } from "@/lib/api";
import { eventLabel, money, shortHash, when } from "@/lib/format";

function SectionTitle({ icon: Icon, children }: { icon: typeof Wallet; children: React.ReactNode }) {
  return (
    <h2 className="flex items-center gap-2 font-display text-base font-semibold tracking-tight">
      <Icon className="size-4 text-muted" aria-hidden />
      {children}
    </h2>
  );
}

export function Sidebar({ data, error }: { data: Dashboard | null; error: string | null }) {
  if (error) {
    return <p className="rounded-xl bg-bad-soft p-4 text-sm text-bad">{error}</p>;
  }
  if (!data) {
    return (
      <div className="space-y-8" aria-busy>
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-28 animate-pulse rounded-xl bg-panel/60" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-9">
      <section>
        <SectionTitle icon={Wallet}>Today&apos;s budget</SectionTitle>
        <div className="mt-4 space-y-4">
          {data.budgets.map((b) => {
            const pct = Math.min(100, (Number(b.spent) / Number(b.limit)) * 100);
            return (
              <div key={b.currency}>
                <div className="flex items-baseline justify-between">
                  <span className="font-display tabular text-2xl font-semibold tracking-tight">{money(b.remaining, b.currency)}</span>
                  <span className="text-xs text-muted">left of {money(b.limit, b.currency)}</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-panel ring-1 ring-line">
                  <div
                    className={`h-full rounded-full transition-[width] duration-700 ${pct > 85 ? "bg-warn" : "bg-ink"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="mt-1.5 text-xs text-faint">Up to {money(b.per_transaction, b.currency)} per payment</p>
              </div>
            );
          })}
        </div>
        <p className="mt-4 text-sm text-muted">
          {data.stats.analyzed} checked today: {data.stats.paid} paid, {data.stats.review} flagged, {data.stats.blocked} blocked.
        </p>
      </section>

      <section>
        <SectionTitle icon={ReceiptText}>Recent payments</SectionTitle>
        {data.transactions.length === 0 ? (
          <p className="mt-3 text-sm text-muted">No payments yet. Approved payments and their receipts show up here.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line">
            {data.transactions.map((t) => (
              <li key={t.id}>
                <Link
                  href={`/receipt?id=${encodeURIComponent(t.receipt_number)}`}
                  className="group flex items-center gap-3 py-2.5"
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[15px] font-medium">{t.recipient || t.recipient_email || "Recipient"}</div>
                    <div className="truncate text-xs text-faint">
                      {t.invoice_number ? `${t.invoice_number}, ` : ""}
                      {when(t.created_at)}
                    </div>
                  </div>
                  <span className="tabular text-[15px] font-semibold">{money(t.amount, t.currency)}</span>
                  <ChevronRight className="size-4 text-faint transition-transform group-hover:translate-x-0.5" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <SectionTitle icon={data.audit.valid ? Link2 : Link2Off}>Audit trail</SectionTitle>
        <div
          className={`mt-3 flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm ${
            data.audit.valid ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad"
          }`}
        >
          <span className="font-medium">
            {data.audit.valid
              ? `${data.audit.count} events, chain intact`
              : `Chain broken at event ${data.audit.broken_at}`}
          </span>
          <code className="ml-auto font-mono text-xs opacity-80" title={data.audit.head}>
            {shortHash(data.audit.head, 8)}
          </code>
        </div>
        {data.audit.events.length > 0 && (
          <ol className="mt-3 space-y-2.5 border-l border-line pl-4">
            {data.audit.events.map((e) => (
              <li key={e.seq} className="relative text-sm">
                <span className="absolute -left-[21px] top-1.5 size-2 rounded-full bg-line ring-2 ring-cloud" aria-hidden />
                <div className="flex justify-between gap-3">
                  <span className="text-ink">{eventLabel(e.event)}</span>
                  <span className="shrink-0 text-xs text-faint">{when(e.ts)}</span>
                </div>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-3 text-xs text-faint">
          Each event is hashed with the one before it, so changing any past record breaks the chain.
        </p>
      </section>
    </div>
  );
}
