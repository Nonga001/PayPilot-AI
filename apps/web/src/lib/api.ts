export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Decision = "approved" | "review" | "blocked";

export interface Check {
  id: string;
  label: string;
  passed: boolean;
  severity: "block" | "review";
  detail: string;
}

export interface Policy {
  decision: Decision;
  risk_level: "low" | "medium" | "high";
  risk_score: number;
  reasons: string[];
  checks: Check[];
  passed: number;
  total: number;
}

export interface Payment {
  amount: string;
  currency: string;
  recipient: string;
  recipient_email: string;
  description: string;
  invoice_number: string;
  confidence: "high" | "medium" | "low";
}

export interface Proposal {
  id: string;
  status: "proposed" | "blocked" | "awaiting_payer" | "completed" | "cancelled" | "failed";
  created_at: string;
  message: string;
  payment: Payment;
  ai: { source: "groq" | "rules"; model: string; latency_ms: number; fallback_reason?: string | null };
  policy: Policy;
  explanation: string;
  order_id: string | null;
  approval_url: string | null;
  timing_ms?: { ai: number; total: number };
}

export interface Transaction {
  id: string;
  receipt_number: string;
  proposal_id: string;
  order_id: string;
  capture_id: string | null;
  status: string;
  amount: string;
  currency: string;
  recipient: string | null;
  recipient_email: string | null;
  description: string | null;
  invoice_number: string | null;
  payer_email: string | null;
  payer_name: string | null;
  paypal_fee: string | null;
  net_amount: string | null;
  decision: Decision | null;
  risk_level: string | null;
  amount_verified: boolean;
  audit_hash: string | null;
  created_at: string;
}

export interface AuditEvent {
  seq: number;
  ts: string;
  event: string;
  proposal_id: string | null;
  data: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface Budget {
  currency: string;
  spent: string;
  limit: string;
  per_transaction: string;
  remaining: string;
}

export interface Dashboard {
  budgets: Budget[];
  limits: Record<string, { per_transaction: string; per_day: string }>;
  stats: { analyzed: number; blocked: number; review: number; paid: number };
  transactions: Transaction[];
  audit: { valid: boolean; count: number; broken_at: number | null; head: string; events: AuditEvent[] };
  environment: { paypal: string; ai_model: string };
}

export interface ReceiptData {
  transaction: Transaction;
  proposal: Proposal | null;
  audit: AuditEvent[];
}

function errorMessage(data: unknown, status: number): string {
  const detail = (data as { detail?: unknown })?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join("; ");
  return `Request failed (${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: init?.body ? { "Content-Type": "application/json" } : undefined,
      cache: "no-store",
    });
  } catch {
    throw new Error(`Can't reach the PayPilot API at ${API_URL}. Is the backend running?`);
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(errorMessage(data, r.status));
  return data as T;
}

const post = <T,>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const api = {
  analyze: (message: string) => post<Proposal>("/agent/analyze", { message }),
  createOrder: (proposal_id: string, acknowledge_risks: boolean) =>
    post<{ order_id: string; approval_url: string; reused: boolean }>("/payments/create-order", {
      proposal_id,
      acknowledge_risks,
    }),
  capture: (order_id: string) =>
    post<{ transaction: Transaction; already_captured: boolean }>("/payments/capture-order", { order_id }),
  cancel: (order_id: string) => post<{ proposal_id: string; status: string }>("/payments/cancel", { order_id }),
  dashboard: () => request<Dashboard>("/dashboard"),
  receipt: (key: string) => request<ReceiptData>(`/transactions/${encodeURIComponent(key)}`),
};
