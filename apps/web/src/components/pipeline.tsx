import { BadgeCheck, CreditCard, FileCheck2, Hand, ListChecks, MessageSquareText, type LucideIcon } from "lucide-react";

const STAGES: { label: string; icon: LucideIcon }[] = [
  { label: "Understand", icon: MessageSquareText },
  { label: "Check", icon: ListChecks },
  { label: "Explain", icon: FileCheck2 },
  { label: "Approve", icon: Hand },
  { label: "Pay", icon: CreditCard },
  { label: "Record", icon: BadgeCheck },
];

/** current = index of the active stage; stopped = the flow halted at `current` (blocked). */
export function Pipeline({ current, stopped = false, working = false }: { current: number; stopped?: boolean; working?: boolean }) {
  return (
    <ol className="flex items-center gap-1 overflow-x-auto text-xs sm:text-[13px]" aria-label="Payment progress">
      {STAGES.map((s, i) => {
        const done = i < current || current >= STAGES.length;
        const active = i === current;
        const Icon = s.icon;
        const tone = done
          ? "text-ok"
          : active
            ? stopped
              ? "text-bad"
              : "text-ink"
            : "text-faint";
        return (
          <li key={s.label} className="flex items-center gap-1" aria-current={active ? "step" : undefined}>
            <span
              className={`flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 ${tone} ${
                active ? (stopped ? "bg-bad-soft" : "bg-panel shadow-sm ring-1 ring-line") : ""
              }`}
            >
              <Icon className={`size-3.5 ${active && working ? "animate-pulse" : ""}`} aria-hidden />
              {s.label}
            </span>
            {i < STAGES.length - 1 && <span className={`h-px w-3 sm:w-5 ${done ? "bg-ok/50" : "bg-line"}`} aria-hidden />}
          </li>
        );
      })}
    </ol>
  );
}
