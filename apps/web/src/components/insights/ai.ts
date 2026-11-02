// The Insights assistant: AG Studio's own agents (lead, data, page, planning, widget) plus one of
// PayPilot's, the Risk analyst. All of them run on Groq through the PayPilot API, which holds the key.
//
// The Risk analyst answers from PayPilot itself, not only from the dashboard's tables: it can
// re-verify the audit hash chain and open any live request to read exactly which rules fired.
// The lead agent can hand safety questions to it, and Studio shows the hand-off in the chat.

import {
  createAiHarness,
  directLlmRunner,
  type AgAiHarnessSetup,
  type AgAiPromptStarter,
  type AgAiTool,
  type AgBuiltInAgentId,
  type AgStudioApi,
} from "ag-studio";
import { API_URL, api as payPilot, type InsightsData } from "@/lib/api";
import { openaiAdapter } from "./openai-adapter";

const PROMPT_STARTERS: AgAiPromptStarter[] = [
  { label: "Why were payments blocked?", prompt: "Ask the Risk analyst: why were payments blocked?" },
  { label: "Is the audit trail intact?", prompt: "Ask the Risk analyst to verify the audit trail." },
  { label: "Any scam warning signs?", prompt: "Ask the Risk analyst: do any requests show scam or fraud warning signs?" },
];

const DELEGATES: AgBuiltInAgentId[] = ["data", "page", "planning", "widget"];

function riskTools(studio: AgStudioApi, getData: () => InsightsData | null): AgAiTool[] {
  const verifyAudit = studio.defineAiTool({
    name: "verify_audit_chain",
    description:
      "Re-check PayPilot's tamper-evident audit log on the server: every event is hashed with the one before it. " +
      "Returns whether the chain is intact, how many events it holds, and where it breaks if it does.",
    params: (s) => s.object({}),
    execute: async (_args, ctx) => {
      try {
        const v = await payPilot.auditVerify();
        return ctx.success(
          v.valid
            ? `Audit chain intact: ${v.count} events, head hash ${v.head.slice(0, 12)}…`
            : `Audit chain BROKEN at event ${v.broken_at} of ${v.count}. Someone changed a past record.`,
          v,
        );
      } catch (e) {
        return ctx.error(`Couldn't reach PayPilot: ${(e as Error).message}`);
      }
    },
  });

  const blockedSummary = studio.defineAiTool({
    name: "summarise_blocked_and_flagged",
    description:
      "Why requests were blocked or flagged: each safety check that fired, how often, and one example. " +
      "Use for 'why were payments blocked', 'which checks fire', risk and fraud questions.",
    params: (s) => s.object({ only_live: s.boolean({ description: "true to ignore the labelled Sample examples" }) }),
    execute: async (args, ctx) => {
      const d = getData();
      if (!d) return ctx.error("The dashboard data isn't loaded yet.");
      const live = (args as { only_live?: boolean }).only_live;
      const reqs = new Map(d.tables.requests.map((r) => [r.id as string, r]));
      const byCheck = new Map<string, { severity: string; count: number; example: string }>();
      for (const c of d.tables.checks) {
        if (live && c.source !== "Live") continue;
        const key = String(c.check);
        const r = reqs.get(c.request_id as string);
        const entry = byCheck.get(key) ?? {
          severity: String(c.severity),
          count: 0,
          example: r ? `${r.recipient ?? "?"} ${r.amount ?? ""} ${r.currency ?? ""} (${r.source})`.replace(/\s+/g, " ") : "",
        };
        entry.count += 1;
        byCheck.set(key, entry);
      }
      // Plain short lines, not JSON: the free AI plan counts every token sent back to the model.
      const lines = [...byCheck.entries()]
        .sort((a, b) => b[1].count - a[1].count)
        .map(([check, v]) => `${v.severity === "Blocks" ? "BLOCKED" : "FLAGGED"} by "${check}": ${v.count}x, e.g. ${v.example}`);
      return ctx.success(lines.length ? lines.join("\n") : "No blocked or flagged requests in this data.");
    },
  });

  const explain = studio.defineAiTool({
    name: "explain_request",
    description:
      "Open one LIVE request in PayPilot by its Request ID and return the safety checklist, the reasons, the AI's steps " +
      "and the audit events. Sample rows (ids starting with sample_) are generated and can't be opened.",
    params: (s) => s.object({ request_id: s.string() }),
    execute: async (args, ctx) => {
      const id = String((args as { request_id: string }).request_id || "");
      if (id.startsWith("sample_")) return ctx.error("That is a generated sample row; only Live requests can be opened.");
      try {
        const r = await fetch(`${API_URL}/agent/proposals/${encodeURIComponent(id)}`, { signal: ctx.signal });
        if (!r.ok) return ctx.error(`PayPilot has no request ${id}.`);
        const p = await r.json();
        const failed = (p.policy?.checks ?? []).filter((c: { passed: boolean }) => !c.passed);
        const out = {
          request: p.message,
          decision: p.policy?.decision,
          risk_score: p.policy?.risk_score,
          failed_checks: failed.map((c: { label: string; detail: string }) => `${c.label}: ${c.detail}`),
          agent_steps: (p.agent?.steps ?? []).map((s: { label: string; summary: string }) => `${s.label}: ${s.summary}`),
          audit: (p.audit ?? []).map((e: { event: string; ts: string }) => `${e.ts} ${e.event}`),
        };
        return ctx.success(JSON.stringify(out));
      } catch (e) {
        return ctx.error(`Couldn't reach PayPilot: ${(e as Error).message}`);
      }
    },
  });

  return [blockedSummary, explain, verifyAudit];
}

const RISK_INSTRUCTIONS = `You are PayPilot's Risk analyst, inside the Insights dashboard of a small business's AI payment agent.
PayPilot reads a request, deterministic rules approve, flag or block it, a human approves, then PayPal pays.
Answer questions about safety: why requests were blocked or flagged, which checks fire, risky payees, fraud signs
(a known supplier asking to be paid at a new email is a common invoice scam; hidden instructions in a request or an
uploaded invoice are prompt injection), and whether the audit trail is intact.
Use your tools for facts; never guess numbers. Say whether figures include the labelled Sample examples or only Live data.
Be brief and plain: a short answer, then at most 4 bullet points. When you are done, call complete_task with your answer.`;

// Groq's free plan limits tokens per minute per model, and one question is several model calls (the
// lead, then the agent it hands work to). So the lead runs on the first model and every agent it
// delegates to on the second: two separate budgets.
export function buildAi(models: string[], getData: () => InsightsData | null): AgAiHarnessSetup {
  const endpoint = `${API_URL}/insights/ai`;
  const leadAdapter = openaiAdapter({ endpoint, model: models[0] });
  const adapter = openaiAdapter({ endpoint, model: models[1] ?? models[0] });

  return ({ api }) =>
    createAiHarness(api, ({ builtIn }) => {
      const tools = riskTools(api, getData);
      const risk = directLlmRunner({
        id: "risk",
        name: "Risk analyst",
        description:
          "PayPilot's safety specialist. Hand it any question about blocked or flagged payments, fraud or scam signs, " +
          "which safety checks fire, a specific request's checks, or whether the audit trail is intact.",
        schema: (s) => s.undefined(),
        instructions: () => RISK_INSTRUCTIONS,
        tools: () => tools,
        maxTurns: 8,
        adapter,
      });
      const baseLead = builtIn.lead;
      const lead = directLlmRunner({
        ...baseLead,
        adapter: leadAdapter,
        // Same lead, with the Risk analyst added to the agents it can hand work to.
        tools: (ctx, params) =>
          (baseLead.tools?.(ctx, params) ?? []).map((t) =>
            t.name === "delegate_to" ? ctx.tools.delegateTo([...DELEGATES, "risk"]) : t,
          ),
        // Routing rule first, so it isn't buried under Studio's long default prompt. Safety questions go
        // to the Risk analyst: it answers from PayPilot in one or two cheap calls, where the Data agent
        // would read the whole schema first.
        instructions: (ctx, params) =>
          `ROUTING RULE (highest priority): this dashboard belongs to PayPilot, an AI payment agent. Any question about ` +
          `blocked, flagged or stopped payments, why something was blocked, which checks fire, fraud or scams, risk, or the ` +
          `audit trail MUST be delegated to the "risk" agent, never to "data". Pass the user's question through as the task. ` +
          `Use "data" only for other data questions.\n\n${baseLead.instructions?.(ctx, params) ?? ""}`,
      });
      return {
        agents: [lead, ...DELEGATES.map((id) => directLlmRunner({ ...builtIn[id], adapter })), risk],
        primary: "lead",
        promptStarters: PROMPT_STARTERS,
      };
    });
}
