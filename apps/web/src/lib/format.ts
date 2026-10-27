const SYMBOLS: Record<string, string> = { USD: "$", EUR: "€", GBP: "£", CAD: "CA$", AUD: "A$" };

export function money(amount: string | number | null | undefined, currency?: string | null): string {
  if (amount === null || amount === undefined || amount === "") return "—";
  const n = Number(amount);
  if (!Number.isFinite(n)) return String(amount);
  const formatted = n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const sym = currency ? SYMBOLS[currency] : undefined;
  return sym ? `${sym}${formatted}` : `${formatted}${currency ? ` ${currency}` : ""}`;
}

export function when(iso: string): string {
  const d = new Date(iso);
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400 && new Date().getDate() === d.getDate()) {
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    year: "numeric", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export function shortHash(h: string | null | undefined, n = 10): string {
  return h ? `${h.slice(0, n)}…` : "—";
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
}

const EVENT_LABELS: Record<string, string> = {
  "request.received": "Instruction received",
  "ai.extracted": "AI read the request",
  "policy.approved": "Checks passed",
  "policy.review": "Flagged for review",
  "policy.blocked": "Blocked by policy",
  "human.approved": "Approved by you",
  "order.created": "PayPal order created",
  "order.failed": "PayPal order failed",
  "payment.captured": "Payment captured",
  "capture.failed": "Capture failed",
  "capture.amount_mismatch": "Amount mismatch flagged",
  "payer.cancelled": "Cancelled on PayPal",
  "execution.refused": "Refused at execution",
};

export const eventLabel = (e: string) => EVENT_LABELS[e] ?? e;
