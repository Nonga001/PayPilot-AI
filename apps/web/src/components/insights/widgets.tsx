"use client";

// PayPilot's own AG Studio widgets. They sit on the canvas like the built-in ones (move, resize,
// title, delete, and the AI can add them), but show things only PayPilot knows:
//   - Safety funnel: how many requests made it from "asked" to "paid", read through Studio's data
//     engine so it follows every filter on the page.
//   - Audit trail: re-verifies the server's SHA-256 hash chain live.

import type { AgWidgetField, AgWidgetParams } from "ag-studio";
import { createWidgets } from "ag-studio-react";
import { Ban, Link2, Loader2, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

const ICON_FUNNEL =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4h18l-7 8v6l-4 2v-8z"/></svg>';
const ICON_SHIELD =
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>';

const MEASURES = ["requests.count", "requests.is_blocked", "requests.is_flagged", "requests.is_paid"] as const;

// Studio returns one row; its keys follow the field ids. Match loosely so a renamed key still works.
function pick(row: Record<string, unknown>, id: string): number {
  const name = id.split(".")[1];
  const key = Object.keys(row).find((k) => k === id || k.endsWith(name) || k.includes(`.${name}`) || k.includes(name));
  const v = key ? Number(row[key]) : 0;
  return Number.isFinite(v) ? v : 0;
}

function SafetyFunnel(params: AgWidgetParams) {
  const { widgetApi } = params;
  const [n, setN] = useState<{ total: number; blocked: number; flagged: number; paid: number } | null>(null);

  useEffect(() => {
    let live = true;
    widgetApi.setDisplayState("loading", { prominent: false } as never);
    // getData wants full field objects: look the columns up in the schema, then sum them.
    const all = widgetApi.getSchema().flatMap((t) => t.fields);
    const fields = MEASURES.map((id) => all.find((f) => String(f.fieldId) === id || String(f.fieldId).endsWith(`.${id.split(".")[1]}`)));
    if (fields.some((f) => !f)) {
      widgetApi.setDisplayState("noData");
      return;
    }
    widgetApi
      .getData({ fields: fields.map((f) => ({ ...f!, type: "implicitMeasure", aggregation: "sum" }) as AgWidgetField) })
      .then((res) => {
        if (!live) return;
        const row = (res.results.rows[0] ?? {}) as Record<string, unknown>;
        const v = { total: pick(row, MEASURES[0]), blocked: pick(row, MEASURES[1]), flagged: pick(row, MEASURES[2]), paid: pick(row, MEASURES[3]) };
        setN(v);
        widgetApi.setDisplayState(v.total ? "displayed" : "noData");
      })
      .catch(() => live && widgetApi.setDisplayState("noData"));
    return () => {
      live = false;
    };
    // Studio hands a new params object whenever filters or the data change.
  }, [params, widgetApi]);

  if (!n || !n.total) return null;
  const cleared = n.total - n.blocked;
  const steps = [
    { label: "Asked", value: n.total, note: "requests typed or uploaded" },
    { label: "Passed the rules", value: cleared, note: `${n.flagged} needed a human check` },
    { label: "Paid through PayPal", value: n.paid, note: "approved by the owner" },
  ];
  return (
    <div className="flex h-full flex-col justify-center gap-2.5 px-1 text-ink">
      {steps.map((s, i) => {
        const pct = Math.round((s.value / n.total) * 100);
        return (
          <div key={s.label} className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{s.label}</div>
              <div className="truncate text-xs text-muted">{s.note}</div>
            </div>
            <div className="h-7 overflow-hidden rounded-lg bg-cloud">
              <div
                className={`h-full rounded-lg ${i === 0 ? "bg-ink" : i === 1 ? "bg-ai" : "bg-ok"}`}
                style={{ width: `${Math.max(pct, 2)}%`, transition: "width 400ms ease" }}
              />
            </div>
            <div className="w-20 text-right tabular-nums">
              <span className="text-base font-semibold">{s.value}</span>
              <span className="ml-1 text-xs text-muted">{pct}%</span>
            </div>
          </div>
        );
      })}
      <div className="mt-1 flex items-center gap-1.5 rounded-lg bg-bad-soft px-2.5 py-1.5 text-xs font-medium text-bad">
        <Ban className="size-3.5" aria-hidden />
        {n.blocked} stopped before any money moved
      </div>
    </div>
  );
}

function AuditChain(params: AgWidgetParams) {
  const { widgetApi } = params;
  const [v, setV] = useState<Awaited<ReturnType<typeof api.auditVerify>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [at, setAt] = useState<Date | null>(null);

  const load = useCallback(
    () =>
      api
        .auditVerify()
        .then((r) => {
          setV(r);
          setError(null);
          setAt(new Date());
        })
        .catch((e: Error) => setError(e.message)),
    [],
  );

  const check = () => {
    setBusy(true);
    load().finally(() => setBusy(false));
  };

  useEffect(() => {
    widgetApi.setDisplayState("displayed");
    load();
  }, [load, widgetApi]);

  const ok = v?.valid;
  return (
    <div className="flex h-full flex-col justify-between gap-2 px-1 text-ink">
      {error ? (
        <p className="text-sm text-bad">{error}</p>
      ) : !v ? (
        <Loader2 className="size-5 animate-spin text-ai" aria-label="Checking" />
      ) : (
        <div className="flex items-start gap-3">
          <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${ok ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad"}`}>
            {ok ? <ShieldCheck className="size-5" aria-hidden /> : <ShieldAlert className="size-5" aria-hidden />}
          </span>
          <div className="min-w-0">
            <div className="font-semibold">{ok ? "Chain intact" : `Broken at event ${v.broken_at}`}</div>
            <div className="text-sm text-muted">
              {v.count} events, each SHA-256 hashed with the one before it. Editing any past record breaks the chain.
            </div>
          </div>
        </div>
      )}
      <div className="flex items-center justify-between gap-2 text-xs text-muted">
        <span className="inline-flex min-w-0 items-center gap-1 font-mono">
          <Link2 className="size-3.5 shrink-0" aria-hidden />
          <span className="truncate">{v ? `${v.head.slice(0, 16)}…` : "…"}</span>
        </span>
        <button
          type="button"
          onClick={check}
          disabled={busy}
          className="inline-flex shrink-0 items-center gap-1 rounded-md px-2 py-1 font-medium text-ai hover:bg-ai-soft disabled:opacity-60"
          title={at ? `Last checked ${at.toLocaleTimeString()}` : undefined}
        >
          <RefreshCw className={`size-3.5 ${busy ? "animate-spin" : ""}`} aria-hidden />
          Verify now
        </button>
      </div>
    </div>
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const noForm = ({ createDefaults }: any) => createDefaults({});

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const SAFETY_FUNNEL: any = {
  id: "paypilot-safety-funnel",
  label: "Safety funnel",
  icon: ICON_FUNNEL,
  comp: SafetyFunnel,
  form: noForm,
  defaultState: { format: { title: { enabled: true, text: "From request to PayPal" } } },
  defaultSize: { width: 16, height: 16 },
  minSize: { width: 8, height: 10 },
  toolbar: ["duplicate", "delete"],
  ai: {
    label: "Safety funnel",
    description: "PayPilot's funnel from requests asked, to requests that passed the safety rules, to payments made, with the number blocked. Follows page filters.",
    usage: "Add when the user asks how many requests were stopped, approved or paid. Needs no field mapping.",
  },
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const AUDIT_CHAIN: any = {
  id: "paypilot-audit-chain",
  label: "Audit trail",
  icon: ICON_SHIELD,
  comp: AuditChain,
  form: noForm,
  defaultState: { format: { title: { enabled: true, text: "Audit trail" } } },
  defaultSize: { width: 8, height: 16 },
  minSize: { width: 6, height: 10 },
  toolbar: ["duplicate", "delete"],
  ai: {
    label: "Audit trail integrity",
    description: "Live check of PayPilot's hash-chained audit log: intact or broken, event count, head hash.",
    usage: "Add when the user asks about tamper evidence, audit or record integrity. Needs no field mapping.",
  },
};

// Studio's default widgets plus PayPilot's, with a "PayPilot" group in the add-widget menu.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const payPilotWidgets = (widgetConfig: any) =>
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  createWidgets<any>({
    additionalTypes: [SAFETY_FUNNEL, AUDIT_CHAIN],
    menu: [...widgetConfig.menu, { label: "PayPilot", widgetIds: [SAFETY_FUNNEL.id, AUDIT_CHAIN.id] }],
  });
