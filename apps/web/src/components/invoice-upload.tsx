"use client";

import { CircleAlert, FileCheck2, ShieldAlert, TriangleAlert, X } from "lucide-react";
import type { InvoiceRead } from "@/lib/api";
import { money } from "@/lib/format";

export const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp";

export const SAMPLES = [
  { file: "1-acme-invoice.pdf", label: "Supplier invoice" },
  { file: "2-acme-new-payment-email.pdf", label: "New payment email" },
  { file: "3-hidden-instruction.pdf", label: "Hidden text in PDF" },
];

const METHOD: Record<InvoiceRead["method"], string> = {
  ai: "read by AI",
  rules: "read by backup parser",
  vision: "read from photo by AI",
};

export function InvoiceReadCard({
  name,
  result,
  error,
  onClose,
}: {
  name: string;
  result: InvoiceRead | null;
  error: string | null;
  onClose: () => void;
}) {
  if (error) {
    return (
      <Card tone="bad" icon={<CircleAlert className="size-4" />} title={`Couldn't read ${name}`} onClose={onClose}>
        <p>{error}</p>
      </Card>
    );
  }
  if (!result) return null;
  const f = result.fields;

  if (result.blocked) {
    return (
      <Card tone="bad" icon={<ShieldAlert className="size-4" />} title="Invoice rejected: hidden instruction found" onClose={onClose}>
        <p>
          <span className="font-medium">{name}</span> contains text aimed at the AI:{" "}
          <q className="font-mono text-[13px]">{result.injection}</q>. PayPilot won&apos;t use this file, and the
          attempt is in the audit log.
        </p>
      </Card>
    );
  }

  return (
    <Card
      tone={result.warnings.length ? "warn" : "ok"}
      icon={<FileCheck2 className="size-4" />}
      title={`Read ${f.invoice_number || name}: request drafted above`}
      onClose={onClose}
    >
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1">
        <Row k="Pay" v={f.vendor || "Not found"} />
        <Row k="Amount" v={f.amount ? money(f.amount, f.currency || "USD") : "Not found"} />
        {f.vendor_email && <Row k="PayPal email" v={f.vendor_email} />}
        {f.due_date && <Row k="Due" v={f.due_date} />}
      </dl>
      {result.warnings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {result.warnings.map((w) => (
            <li key={w} className="flex gap-1.5">
              <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              {w}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-xs opacity-80">
        {result.type.toUpperCase()}, {METHOD[result.method]} in {result.ms} ms. Nothing is paid until you send the request,
        the checks pass and you approve.
      </p>
    </Card>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <>
      <dt className="opacity-75">{k}</dt>
      <dd className="min-w-0 truncate font-medium">{v}</dd>
    </>
  );
}

const TONES = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
};

function Card({
  tone,
  icon,
  title,
  onClose,
  children,
}: {
  tone: keyof typeof TONES;
  icon: React.ReactNode;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  return (
    <div role="status" className={`tick-in mt-3 rounded-2xl px-4 py-3 text-sm ${TONES[tone]}`}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5 shrink-0" aria-hidden>
          {icon}
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{title}</p>
          <div className="mt-1 text-ink/90">{children}</div>
        </div>
        <button type="button" onClick={onClose} className="shrink-0 rounded p-0.5 opacity-70 hover:opacity-100" aria-label="Dismiss">
          <X className="size-4" />
        </button>
      </div>
    </div>
  );
}
