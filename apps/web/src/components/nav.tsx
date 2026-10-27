"use client";

import { BookUser, Send, Table2 } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Pay", icon: Send },
  { href: "/ledger", label: "Ledger", icon: Table2 },
  { href: "/payees", label: "Payees", icon: BookUser },
];

export function Nav() {
  const path = usePathname();
  return (
    <nav aria-label="Main" className="flex items-center gap-1 rounded-full bg-panel p-1 ring-1 ring-line">
      {LINKS.map(({ href, label, icon: Icon }) => {
        const active = href === "/" ? path === "/" : path.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition-colors ${
              active ? "bg-ink text-white" : "text-muted hover:text-ink"
            }`}
          >
            <Icon className="size-3.5" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
