"use client";

import {
  ArrowLeft,
  ArrowRight,
  BookUser,
  CalendarClock,
  CircleAlert,
  CircleCheck,
  CircleX,
  FileText,
  Hash,
  Loader2,
  Lock,
  Mail,
  MessageCircle,
  PencilLine,
  Sparkles,
  Timer,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";
import type { Check, Policy, Proposal } from "@/lib/api";
import { RAIL_LABEL, initials, money } from "@/lib/format";
import { AgentSteps } from "./agent-steps";
import { DECISION, DecisionBadge } from "./ui";

function Field({ icon: Icon, label, value }: { icon: typeof FileText; label: string; value: string }) {
  return (
    <div className="flex min-w-0 items-start gap-2.5">
      <Icon className="mt-0.5 size-4 shrink-0 text-faint" aria-hidden />
      <div className="min-w-0">
        <div className="text-xs text-faint">{label}</div>
        <div className={`truncate text-[15px] ${value ? "text-ink" : "italic text-faint"}`}>{value || "Not stated"}</div>
      </div>
    </div>
  );
}

function CheckRow({ c, index }: { c: Check; index: number }) {
  const Icon = c.passed ? CircleCheck : c.severity === "block" ? CircleX : CircleAlert;
  const tone = c.passed ? "text-ok" : c.severity === "block" ? "text-bad" : "text-warn";
  return (
    <li className="tick-in flex items-start gap-3 py-2.5" style={{ animationDelay: `${index * 85}ms` }}>
      <Icon className={`mt-0.5 size-[18px] shrink-0 ${tone}`} aria-hidden />
      <div className="min-w-0">
        <div className="text-[15px] font-medium">
          {c.label}
          <span className="sr-only">: {c.passed ? "passed" : c.severity === "block" ? "failed" : "needs review"}</span>
        </div>
        <div className={`text-sm ${c.passed ? "text-muted" : tone}`}>{c.detail}</div>
      </div>
    </li>
  );
}

function AiMeta({ proposal }: { proposal: Proposal }) {
  const { ai } = proposal;
  return (
    <span className="flex items-center gap-1.5 text-xs text-faint">
      <Timer className="size-3.5" aria-hidden />
      {ai.source === "groq" ? ai.model.replace("openai/", "") : "Backup parser"}, {ai.latency_ms} ms
    </span>
  );
}

export function AnswerView({ proposal, onEdit }: { proposal: Proposal; onEdit: () => void }) {
  return (
    <div className="space-y-8">
      <section className="rounded-2xl bg-ai-soft p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-sm font-medium text-ai">
            <MessageCircle className="size-4" aria-hidden />
            PayPilot&apos;s answer
          </h2>
          <AiMeta proposal={proposal} />
        </div>
        <p className="mt-3 text-lg leading-relaxed text-ink">{proposal.agent.answer}</p>
        <p className="mt-3 text-xs text-muted">Nothing was paid or sent. Questions never move money.</p>
      </section>
      <AgentSteps steps={proposal.agent.steps} source={proposal.ai.source} ms={proposal.ai.latency_ms} />
      <button type="button" onClick={onEdit} className="inline-flex items-center gap-2 text-sm font-medium text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden />
        Ask or pay something else
      </button>
    </div>
  );
}

export function ProposalView({
  proposal,
  onApprove,
  onEdit,
  paying,
}: {
  proposal: Proposal;
  onApprove: (acknowledge: boolean) => void;
  onEdit: () => void;
  paying: boolean;
}) {
  const [ack, setAck] = useState(false);
  const { payment: pay, ai } = proposal;
  const policy = proposal.policy as Policy;
  const d = DECISION[policy.decision];
  const isInvoice = proposal.kind === "invoice";
  const counterpart = pay.recipient || pay.recipient_email || "Unknown recipient";
  const failed = policy.checks.filter((c) => !c.passed);
  const amount = money(pay.amount, pay.currency);
  const action = isInvoice
    ? `Approve and send ${amount} invoice`
    : proposal.rail === "payout"
      ? `Approve and send ${amount}`
      : `Approve and pay ${amount}`;

  return (
    <div className="space-y-8">
      {/* What the agent understood */}
      <section aria-labelledby="plan-heading">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="plan-heading" className="flex items-center gap-2 text-sm font-medium text-ai">
            <Sparkles className="size-4" aria-hidden />
            {isInvoice ? "Invoice to send" : "Payment to make"}
          </h2>
          <AiMeta proposal={proposal} />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-3">
          <span className="font-display tabular text-5xl font-semibold tracking-tight sm:text-6xl">
            {pay.amount ? amount : "?"}
          </span>
          {isInvoice ? (
            <ArrowLeft className="size-7 text-faint" aria-label="from" />
          ) : (
            <ArrowRight className="size-7 text-faint" aria-label="to" />
          )}
          <span className="flex min-w-0 items-center gap-3">
            <span className="grid size-11 shrink-0 place-items-center rounded-full bg-ai-soft font-display text-base font-semibold text-ai">
              {initials(counterpart)}
            </span>
            <span className="min-w-0">
              <span className="block truncate font-display text-2xl font-semibold tracking-tight">{counterpart}</span>
              <span className="flex flex-wrap items-center gap-x-2 text-sm text-muted">
                {proposal.payee ? (
                  <span className="inline-flex items-center gap-1 text-ok">
                    <BookUser className="size-3.5" aria-hidden />
                    Saved {isInvoice ? "contact" : "payee"}
                  </span>
                ) : (
                  <span>New {isInvoice ? "client" : "recipient"}</span>
                )}
                {proposal.rail && <span>by {RAIL_LABEL[proposal.rail]}</span>}
              </span>
            </span>
          </span>
        </div>

        <div className="mt-6 grid gap-4 border-t border-line pt-5 sm:grid-cols-3">
          <Field icon={FileText} label={isInvoice ? "For" : "Purpose"} value={pay.description} />
          {isInvoice ? (
            <Field icon={CalendarClock} label="Due" value="10 days after sending" />
          ) : (
            <Field icon={Hash} label="Invoice" value={pay.invoice_number} />
          )}
          <Field icon={Mail} label="PayPal email" value={pay.recipient_email} />
        </div>
      </section>

      <AgentSteps steps={proposal.agent.steps} source={ai.source} ms={ai.latency_ms} />

      {/* Plain-language explanation */}
      <section className={`rounded-2xl p-5 ${d.bg}`} aria-labelledby="explain-heading">
        <h2 id="explain-heading" className="sr-only">
          What will happen
        </h2>
        <div className="flex items-start gap-3">
          <d.icon className={`mt-0.5 size-5 shrink-0 ${d.text}`} aria-hidden />
          <p className="text-[15px] leading-relaxed text-ink">{proposal.explanation}</p>
        </div>
      </section>

      {/* Checklist */}
      <section aria-labelledby="checks-heading">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="checks-heading" className="font-display text-xl font-semibold tracking-tight">
              Safety checklist
            </h2>
            <p className="text-sm text-muted">
              {policy.passed} of {policy.total} passed. These rules run on the server, not in the AI.
            </p>
          </div>
          <RiskMeter score={policy.risk_score} decision={policy.decision} />
        </div>
        {failed.length > 0 && (
          <ul className="mt-3 divide-y divide-line border-b border-line">
            {failed.map((c, i) => (
              <CheckRow key={c.id} c={c} index={i} />
            ))}
          </ul>
        )}
        <ul className="mt-2 grid gap-x-8 sm:grid-cols-2">
          {policy.checks
            .filter((c) => c.passed)
            .map((c, i) => (
              <CheckRow key={c.id} c={c} index={failed.length + i} />
            ))}
        </ul>
      </section>

      {/* Decision + approval */}
      <section className={`rounded-2xl bg-panel p-5 ring-1 ${d.ring}`} aria-live="polite">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <DecisionBadge decision={policy.decision} size="lg" />
          <span className="text-xs text-faint">Proposal {proposal.id.slice(-8)}</span>
        </div>

        {policy.decision === "blocked" ? (
          <div className="mt-4">
            <p className="text-[15px] text-ink">This can&apos;t go ahead. Change the request and check it again.</p>
            <button
              type="button"
              onClick={onEdit}
              className="mt-4 inline-flex items-center gap-2 rounded-xl bg-cloud px-4 py-2.5 text-sm font-semibold ring-1 ring-line hover:ring-faint"
            >
              <PencilLine className="size-4" aria-hidden />
              Edit request
            </button>
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            {policy.decision === "review" && (
              <label className="flex cursor-pointer items-start gap-3 rounded-xl bg-warn-soft p-3.5 text-[15px]">
                <input
                  type="checkbox"
                  checked={ack}
                  onChange={(e) => setAck(e.target.checked)}
                  className="mt-1 size-4 accent-[var(--color-warn)]"
                />
                <span>
                  I&apos;ve checked the flagged details and want to continue.
                  <span className="mt-0.5 flex items-center gap-1 text-sm text-warn">
                    <TriangleAlert className="size-3.5" aria-hidden />
                    Your confirmation is saved to the audit trail.
                  </span>
                </span>
              </label>
            )}
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                disabled={paying || (policy.decision === "review" && !ack)}
                onClick={() => onApprove(policy.decision === "review")}
                className={`inline-flex items-center gap-2 rounded-xl px-5 py-3 text-[15px] font-semibold text-white transition-opacity disabled:cursor-not-allowed disabled:opacity-45 ${d.solid}`}
              >
                {paying ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Lock className="size-4" aria-hidden />}
                {paying ? (proposal.rail === "checkout" ? "Opening PayPal…" : "Sending with PayPal…") : action}
              </button>
              <button type="button" onClick={onEdit} className="px-2 py-3 text-sm font-medium text-muted hover:text-ink">
                Edit request
              </button>
            </div>
            <p className="text-xs text-faint">
              {proposal.rail === "checkout"
                ? "You'll confirm once more on PayPal."
                : isInvoice
                  ? "PayPal emails the invoice to your client."
                  : "Sent straight from your PayPal business balance."}{" "}
              Sandbox mode: no real money moves.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

function RiskMeter({ score, decision }: { score: number; decision: Policy["decision"] }) {
  const d = DECISION[decision];
  return (
    <div className="w-40" aria-label={`Risk score ${score} out of 100`}>
      <div className="flex justify-between text-xs">
        <span className="text-faint">Risk</span>
        <span className={`tabular font-semibold ${d.text}`}>{score}/100</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-cloud">
        <div className={`h-full rounded-full ${d.solid} transition-[width] duration-700`} style={{ width: `${Math.max(4, score)}%` }} />
      </div>
    </div>
  );
}
