"use client";

import { CircleX } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Composer } from "@/components/composer";
import { Pipeline } from "@/components/pipeline";
import { ProposalView } from "@/components/proposal-view";
import { Shell } from "@/components/shell";
import { Sidebar } from "@/components/sidebar";
import { api, type Dashboard, type Proposal } from "@/lib/api";

type Phase = "idle" | "analyzing" | "proposed" | "paying";

export default function Home() {
  const [message, setMessage] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [dashError, setDashError] = useState<string | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    try {
      setDash(await api.dashboard());
      setDashError(null);
    } catch (e) {
      setDashError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    let live = true;
    api
      .dashboard()
      .then((d) => live && setDash(d))
      .catch((e: Error) => live && setDashError(e.message));
    return () => {
      live = false;
    };
  }, []);

  async function analyze() {
    setPhase("analyzing");
    setError(null);
    setProposal(null);
    try {
      const p = await api.analyze(message);
      setProposal(p);
      setPhase("proposed");
      refresh();
      requestAnimationFrame(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (e) {
      setError((e as Error).message);
      setPhase("idle");
    }
  }

  async function approve(acknowledge: boolean) {
    if (!proposal) return;
    setPhase("paying");
    setError(null);
    try {
      const order = await api.createOrder(proposal.id, acknowledge);
      window.location.assign(order.approval_url);
    } catch (e) {
      setError((e as Error).message);
      setPhase("proposed");
      refresh();
    }
  }

  function edit() {
    setProposal(null);
    setPhase("idle");
    setError(null);
    document.getElementById("instruction")?.focus();
  }

  const decision = proposal?.policy.decision;
  const stage =
    phase === "analyzing" ? 0 : phase === "paying" ? 4 : proposal ? (decision === "blocked" ? 1 : 3) : 0;

  return (
    <Shell model={dash?.environment.ai_model}>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,1fr)_340px] lg:gap-10">
        <div className="min-w-0 rounded-3xl bg-panel shadow-[0_1px_2px_rgba(20,32,51,0.06),0_16px_40px_-20px_rgba(20,32,51,0.25)] ring-1 ring-line">
          <div className="border-b border-line px-5 py-3.5 sm:px-8">
            <Pipeline current={stage} stopped={decision === "blocked" && phase === "proposed"} working={phase === "analyzing"} />
          </div>

          <div className="space-y-10 px-5 py-7 sm:px-8 sm:py-9">
            <Composer value={message} onChange={setMessage} onSubmit={analyze} busy={phase === "analyzing"} />

            {error && (
              <p role="alert" className="flex items-start gap-2 rounded-xl bg-bad-soft p-3.5 text-sm text-bad">
                <CircleX className="mt-0.5 size-4 shrink-0" aria-hidden />
                {error}
              </p>
            )}

            {proposal && (
              <div ref={resultRef} className="scroll-mt-6 border-t border-line pt-9">
                <ProposalView key={proposal.id} proposal={proposal} onApprove={approve} onEdit={edit} paying={phase === "paying"} />
              </div>
            )}
          </div>
        </div>

        <aside className="min-w-0 lg:pt-2">
          <Sidebar data={dash} error={dashError} />
        </aside>
      </div>
    </Shell>
  );
}
