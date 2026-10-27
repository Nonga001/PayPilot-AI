import {
  CircleAlert,
  FileSearch,
  FileText,
  History,
  MessageCircle,
  Send,
  UserSearch,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import type { AgentStep } from "@/lib/api";

const ICONS: Record<string, LucideIcon> = {
  find_payee: UserSearch,
  check_payment_history: History,
  get_budget: Wallet,
  search_paypal_invoices: FileSearch,
  propose_payment: Send,
  propose_invoice: FileText,
  answer: MessageCircle,
};

const FINAL = new Set(["propose_payment", "propose_invoice", "answer"]);

export function AgentSteps({ steps, source, ms }: { steps: AgentStep[]; source: string; ms: number }) {
  if (!steps.length) return null;
  return (
    <section aria-labelledby="steps-heading">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="steps-heading" className="font-display text-base font-semibold tracking-tight">
          How PayPilot worked it out
        </h2>
        <span className="text-xs text-faint">
          {steps.length} {steps.length === 1 ? "step" : "steps"} in {ms} ms{source === "rules" ? ", backup parser" : ""}
        </span>
      </div>
      <ol className="mt-3 space-y-0">
        {steps.map((s, i) => {
          const Icon = s.ok ? (ICONS[s.tool] ?? FileSearch) : CircleAlert;
          const last = i === steps.length - 1;
          const final = FINAL.has(s.tool);
          return (
            <li key={i} className="tick-in grid grid-cols-[1.75rem_1fr_auto] gap-x-3" style={{ animationDelay: `${i * 70}ms` }}>
              <span className="flex flex-col items-center" aria-hidden>
                <span
                  className={`grid size-7 place-items-center rounded-full ${
                    s.ok ? (final ? "bg-ink text-white" : "bg-ai-soft text-ai") : "bg-warn-soft text-warn"
                  }`}
                >
                  <Icon className="size-3.5" />
                </span>
                {!last && <span className="w-px flex-1 bg-line" />}
              </span>
              <div className={`min-w-0 ${last ? "pb-1" : "pb-3"}`}>
                <div className="text-[15px] font-medium">
                  {s.label}
                  {s.auto && <span className="ml-2 text-xs font-normal text-faint">run by PayPilot</span>}
                </div>
                <div className="text-sm text-muted">{s.summary}</div>
              </div>
              {s.ms > 0 && <span className="pt-1 text-xs tabular text-faint">{s.ms} ms</span>}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
