"use client";

import type { AgStudioApi, AgStudioMode } from "ag-studio";
import { FlaskConical, Loader2, PencilRuler, RotateCcw, Sparkles } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import { PAGE_TITLES } from "@/components/insights/report";
import { Shell } from "@/components/shell";
import { api, type InsightsData } from "@/lib/api";

// AG Studio (grid, charts and data engine) is large: load it only here, only in the browser.
const InsightsStudio = dynamic(() => import("@/components/insights/insights-studio").then((m) => m.InsightsStudio), {
  ssr: false,
  loading: () => <Loading />,
});

function Loading() {
  return (
    <div className="grid h-full place-items-center">
      <Loader2 className="size-7 animate-spin text-ai" aria-label="Loading dashboard" />
    </div>
  );
}

export default function InsightsPage() {
  const [sample, setSample] = useState(true);
  const [data, setData] = useState<InsightsData | null>(null);
  // undefined while checking; null when the API has no Groq key (the assistant is then hidden)
  const [aiModels, setAiModels] = useState<string[] | null | undefined>(undefined);
  const aiModel = aiModels === undefined ? undefined : (aiModels?.[0] ?? null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<AgStudioMode>("view");
  const [page, setPage] = useState("safety");
  const [key, setKey] = useState(0);
  const studio = useRef<AgStudioApi | null>(null);

  useEffect(() => {
    api
      .insightsAi()
      .then((s) => setAiModels(s.enabled ? (s.models?.length ? s.models : [s.model]) : null))
      .catch(() => setAiModels(null));
  }, []);

  useEffect(() => {
    let live = true;
    api
      .insights(sample)
      .then((d) => live && (setData(d), setError(null)))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [sample, key]);

  // Studio shows its AI chat and editing panels in edit mode. "Ask AI" opens only the chat, so the
  // dashboard keeps most of the width; "Edit" opens everything.
  function openPanels(which: "ai" | "edit") {
    setMode("edit");
    const closed = which === "ai";
    // Studio applies the mode change on its next render, then lays out the panels; set them after that.
    setTimeout(() => {
      const s = studio.current;
      if (!s) return;
      const st = s.getState();
      s.setState({
        ...st,
        panels: { ...st.panels, ai: { collapsed: false }, edit: { collapsed: closed }, data: { collapsed: closed } },
      });
    }, 60);
  }

  function goTo(id: string) {
    setPage(id);
    const s = studio.current;
    if (s) s.setState({ ...s.getState(), selectedPageId: id });
  }

  const liveTotal = data ? data.live_counts.requests : 0;

  return (
    <Shell model={aiModel ?? undefined}>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h1 className="font-display text-3xl font-semibold tracking-tight">Insights</h1>
          <p className="mt-1 text-[15px] text-muted">
            What PayPilot stopped, flagged and paid. Built with AG Studio: filter anything, switch to Edit to build your own
            widgets, or ask the assistant.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label
            className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-panel px-3 py-1.5 text-sm ring-1 ring-line"
            title="Adds one labelled example of each outcome (paid, flagged, blocked, invoiced, answered). Examples never touch the ledger."
          >
            <input type="checkbox" checked={sample} onChange={(e) => setSample(e.target.checked)} className="accent-[var(--color-ai)]" />
            <FlaskConical className="size-3.5 text-warn" aria-hidden />
            Examples
          </label>
          {aiModel && (
            <button
              type="button"
              onClick={() => openPanels("ai")}
              className="inline-flex items-center gap-1.5 rounded-full bg-ai px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-[#087a97]"
            >
              <Sparkles className="size-3.5" aria-hidden />
              Ask AI
            </button>
          )}
          <button
            type="button"
            onClick={() => (mode === "edit" ? setMode("view") : openPanels("edit"))}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium ring-1 transition-colors ${
              mode === "edit" ? "bg-ink text-white ring-ink" : "bg-panel text-muted ring-line hover:text-ink"
            }`}
            aria-pressed={mode === "edit"}
          >
            <PencilRuler className="size-3.5" aria-hidden />
            {mode === "edit" ? "Done editing" : "Edit"}
          </button>
          <button
            type="button"
            onClick={() => {
              setKey((k) => k + 1);
              setMode("view");
            }}
            className="inline-flex items-center gap-1.5 rounded-full bg-panel px-3 py-1.5 text-sm text-muted ring-1 ring-line hover:text-ink"
            title="Reload the data and the default layout"
          >
            <RotateCcw className="size-3.5" aria-hidden />
            Reset
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Dashboard pages" className="flex gap-1 rounded-full bg-panel p-1 ring-1 ring-line">
          {Object.entries(PAGE_TITLES).map(([id, label]) => (
            <button
              key={id}
              role="tab"
              aria-selected={page === id}
              onClick={() => goTo(id)}
              className={`rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
                page === id ? "bg-ai text-white" : "text-muted hover:text-ink"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="text-xs text-faint">
          {data
            ? `${liveTotal} live ${liveTotal === 1 ? "request" : "requests"}${data.includes_sample ? " + examples" : ""}`
            : ""}
          {aiModel ? (
            <span className="ml-2 inline-flex items-center gap-1 text-ai">
              <Sparkles className="size-3" aria-hidden /> Assistant on {aiModel.replace("openai/", "")}
            </span>
          ) : null}
        </p>
      </div>

      <div className="mt-3 h-[calc(100dvh-13rem)] min-h-[640px] overflow-hidden rounded-2xl ring-1 ring-line">
        {error ? (
          <div className="grid h-full place-items-center p-6 text-center text-bad">{error}</div>
        ) : !data || aiModel === undefined ? (
          <Loading />
        ) : (
          <InsightsStudio
            key={`${key}-${sample}`}
            data={data}
            mode={mode}
            aiModels={aiModels ?? null}
            pageId={page}
            onApi={(a) => (studio.current = a)}
          />
        )}
      </div>
    </Shell>
  );
}
