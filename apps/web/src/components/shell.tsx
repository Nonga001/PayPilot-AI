import { FlaskConical, Sparkles } from "lucide-react";
import Link from "next/link";
import { Nav } from "./nav";
import { Logo } from "./ui";

export function Shell({ children, model }: { children: React.ReactNode; model?: string }) {
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-[1240px] flex-col px-4 pb-10 sm:px-6 lg:px-8">
      <header className="no-print flex flex-wrap items-center justify-between gap-3 py-5">
        <Link href="/" aria-label="PayPilot home">
          <Logo />
        </Link>
        <div className="order-3 w-full sm:order-none sm:w-auto">
          <Nav />
        </div>
        <div className="flex items-center gap-2 text-xs">
          {model && (
            <span className="hidden items-center gap-1.5 rounded-full bg-panel px-2.5 py-1 text-muted ring-1 ring-line md:inline-flex">
              <Sparkles className="size-3.5 text-ai" aria-hidden />
              {model.replace("openai/", "")}
            </span>
          )}
          <span className="inline-flex items-center gap-1.5 rounded-full bg-warn-soft px-2.5 py-1 font-medium text-warn" title="AI reads the request. Rules decide. You approve.">
            <FlaskConical className="size-3.5" aria-hidden />
            PayPal Sandbox
          </span>
        </div>
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
