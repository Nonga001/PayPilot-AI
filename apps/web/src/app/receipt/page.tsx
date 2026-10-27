"use client";

import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Receipt } from "@/components/receipt";
import { Shell } from "@/components/shell";
import { api, type ReceiptData } from "@/lib/api";

function ReceiptLoader() {
  const id = useSearchParams().get("id");
  const [data, setData] = useState<ReceiptData | null>(null);
  const [error, setError] = useState<string | null>(id ? null : "No receipt selected.");

  useEffect(() => {
    if (!id) return;
    api.receipt(id).then(setData).catch((e: Error) => setError(e.message));
  }, [id]);

  if (error) {
    return (
      <div className="mx-auto max-w-lg rounded-3xl bg-panel p-8 ring-1 ring-line">
        <h1 className="font-display text-2xl font-semibold">Receipt not found</h1>
        <p className="mt-2 text-[15px] text-muted">{error}</p>
        <Link href="/" className="mt-6 inline-block rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white">
          Back to PayPilot
        </Link>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="grid place-items-center py-24">
        <Loader2 className="size-7 animate-spin text-ai" aria-label="Loading receipt" />
      </div>
    );
  }
  return <Receipt data={data} />;
}

export default function ReceiptPage() {
  return (
    <Shell>
      <Suspense fallback={null}>
        <ReceiptLoader />
      </Suspense>
    </Shell>
  );
}
