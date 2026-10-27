"use client";

import { CircleX, Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Receipt } from "@/components/receipt";
import { Shell } from "@/components/shell";
import { api, type ReceiptData } from "@/lib/api";

function Capture() {
  const token = useSearchParams().get("token");
  const [data, setData] = useState<ReceiptData | null>(null);
  const [error, setError] = useState<string | null>(token ? null : "PayPal didn't return an order token.");
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true; // React strict mode runs effects twice in dev; capture once
    (async () => {
      try {
        const { transaction } = await api.capture(token);
        setData(await api.receipt(transaction.receipt_number));
        window.history.replaceState(null, "", `/receipt?id=${encodeURIComponent(transaction.receipt_number)}`);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, [token]);

  if (error) {
    return (
      <div className="mx-auto max-w-lg rounded-3xl bg-panel p-8 ring-1 ring-line">
        <h1 className="flex items-center gap-2 font-display text-2xl font-semibold text-bad">
          <CircleX className="size-6" aria-hidden />
          Payment not completed
        </h1>
        <p className="mt-2 text-[15px] text-muted">{error}</p>
        <Link href="/" className="mt-6 inline-block rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white">
          Back to PayPilot
        </Link>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="mx-auto flex max-w-lg flex-col items-center gap-3 py-24 text-center" aria-live="polite">
        <Loader2 className="size-8 animate-spin text-ai" aria-hidden />
        <p className="font-display text-xl font-semibold">Completing your payment</p>
        <p className="text-sm text-muted">Capturing with PayPal and writing the receipt.</p>
      </div>
    );
  }
  return <Receipt data={data} fresh />;
}

export default function SuccessPage() {
  return (
    <Shell>
      <Suspense fallback={null}>
        <Capture />
      </Suspense>
    </Shell>
  );
}
