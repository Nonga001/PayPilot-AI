import { ShieldAlert, ShieldCheck, ShieldX, type LucideIcon } from "lucide-react";
import type { Decision } from "@/lib/api";

export const DECISION: Record<
  Decision,
  { label: string; short: string; icon: LucideIcon; text: string; bg: string; ring: string; solid: string }
> = {
  approved: {
    label: "Cleared to pay",
    short: "Cleared",
    icon: ShieldCheck,
    text: "text-ok",
    bg: "bg-ok-soft",
    ring: "ring-ok/25",
    solid: "bg-ok",
  },
  review: {
    label: "Needs your review",
    short: "Review",
    icon: ShieldAlert,
    text: "text-warn",
    bg: "bg-warn-soft",
    ring: "ring-warn/25",
    solid: "bg-warn",
  },
  blocked: {
    label: "Blocked",
    short: "Blocked",
    icon: ShieldX,
    text: "text-bad",
    bg: "bg-bad-soft",
    ring: "ring-bad/25",
    solid: "bg-bad",
  },
};

export function DecisionBadge({ decision, size = "sm" }: { decision: Decision; size?: "sm" | "lg" }) {
  const d = DECISION[decision];
  const Icon = d.icon;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full ring-1 ${d.bg} ${d.text} ${d.ring} ${
        size === "lg" ? "px-3 py-1.5 text-sm font-semibold" : "px-2 py-0.5 text-xs font-medium"
      }`}
    >
      <Icon className={size === "lg" ? "size-4" : "size-3.5"} aria-hidden />
      {size === "lg" ? d.label : d.short}
    </span>
  );
}

export function Logo() {
  return (
    <span className="flex items-center gap-2.5">
      <span className="grid size-9 place-items-center rounded-[10px] bg-ink text-white shadow-[inset_0_-2px_0_rgba(255,255,255,0.12)]">
        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
          <circle cx="12" cy="12" r="8.5" opacity="0.45" />
          <path d="M12 4.5 15 13l-3-1.6L9 13z" fill="currentColor" stroke="none" />
          <path d="M12 15.5v4" strokeLinecap="round" />
        </svg>
      </span>
      <span className="font-display text-[1.2rem] font-semibold tracking-tight">PayPilot</span>
    </span>
  );
}
