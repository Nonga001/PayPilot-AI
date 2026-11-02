"use client";

import { Sparkles } from "lucide-react";
import { useApiHealth } from "@/lib/health";

// Which AI is reading requests, on every page.
export function ModelBadge({ model: given }: { model?: string }) {
  const health = useApiHealth();
  if (!given && health.status !== "ok") return null;
  const model = given ?? health.model;
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
