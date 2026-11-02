"use client";

import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

// Which AI is reading requests, on every page. One /health call per visit, shared by all pages.
let cached: Promise<string | null> | null = null;
const loadModel = () =>
  (cached ??= fetch(`${API_URL}/health`, { cache: "no-store" })
    .then((r) => r.json())
    .then((h: { ai_model?: string | null }) => h.ai_model ?? null)
    .catch(() => {
      cached = null; // API asleep or unreachable: try again on the next page
      return null;
    }));

export function ModelBadge({ model: given }: { model?: string }) {
  const [loaded, setLoaded] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    if (given) return;
    let live = true;
    loadModel().then((m) => live && setLoaded(m));
    return () => {
      live = false;
    };
  }, [given]);

  const model = given ?? loaded;
  if (model === undefined) return null;
  const label = model ? model.replace("openai/", "") : "Backup parser";
  return (
    <span
      className="hidden items-center gap-1.5 rounded-full bg-panel px-2.5 py-1 text-muted ring-1 ring-line sm:inline-flex"
      title={model ? `Requests are read by ${model} on Groq` : "No AI key: a rule-based parser reads requests"}
    >
      <Sparkles className={`size-3.5 ${model ? "text-ai" : "text-faint"}`} aria-hidden />
      {label}
    </span>
  );
}
