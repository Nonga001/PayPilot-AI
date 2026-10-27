"use client";

import { CircleSlash } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";
import { Shell } from "@/components/shell";
import { api } from "@/lib/api";

function Cancelled() {
  const token = useSearchParams().get("token");
  const sent = useRef(false);
  useEffect(() => {
    if (token && !sent.current) {
      sent.current = true;
      api.cancel(token).catch(() => {});
    }
  }, [token]);

  return (
    <div className="mx-auto max-w-lg rounded-3xl bg-panel p-8 ring-1 ring-line">
      <h1 className="flex items-center gap-2 font-display text-2xl font-semibold">
        <CircleSlash className="size-6 text-warn" aria-hidden />
        Payment cancelled
      </h1>
      <p className="mt-2 text-[15px] text-muted">
        You stopped this payment on PayPal, so no money moved. The cancellation is in the audit trail.
      </p>
      <Link href="/" className="mt-6 inline-block rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white">
        Start a new payment
      </Link>
    </div>
  );
}

export default function CancelPage() {
  return (
    <Shell>
      <Suspense fallback={null}>
        <Cancelled />
      </Suspense>
    </Shell>
  );
}
