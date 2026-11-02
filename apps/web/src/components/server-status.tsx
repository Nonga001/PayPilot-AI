"use client";

import { CircleCheck, Loader2, PlugZap } from "lucide-react";
import { useEffect, useState } from "react";
import { useApiHealth } from "@/lib/health";

// A slim banner under the header while the API is waking up (Render's free plan sleeps when idle).
// Hidden when the API answers quickly, which is the usual case.
export function ServerStatus() {
  const h = useApiHealth();
  const [now, setNow] = useState(0);

  useEffect(() => {
    if (h.status !== "waking" && h.status !== "down") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [h.status]);

  if (h.status === "ok" && h.woke) {
    return (
      <div role="status" className="tick-in no-print mb-4 flex items-center gap-2 rounded-xl bg-ok-soft px-4 py-2.5 text-sm text-ok">
        <CircleCheck className="size-4 shrink-0" aria-hidden />
        Server is awake. You&apos;re good to go.
      </div>
    );
  }
  if (h.status !== "waking" && h.status !== "down") return null;

  const seconds = now && h.since ? Math.max(0, Math.round((now - h.since) / 1000)) : 0;
  const down = h.status === "down";
  return (
    <div
      role="status"
      aria-live="polite"
      className={`no-print mb-4 flex items-start gap-2.5 rounded-xl px-4 py-2.5 text-sm ${down ? "bg-bad-soft text-bad" : "bg-warn-soft text-warn"}`}
    >
      {down ? <PlugZap className="mt-0.5 size-4 shrink-0" aria-hidden /> : <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin" aria-hidden />}
      <div className="min-w-0">
        <p className="font-medium">
          {down ? "The PayPilot server isn't answering yet." : "Waking up the PayPilot server…"}
          {seconds > 0 && <span className="ml-1.5 font-normal tabular-nums opacity-80">{seconds}s</span>}
        </p>
        <p className="text-ink/75">
          {down
            ? "Still trying every few seconds. If this lasts more than two minutes, refresh the page."
            : "The free hosting plan sleeps when nobody is using it. This takes up to a minute, then everything loads by itself."}
        </p>
      </div>
    </div>
  );
}
