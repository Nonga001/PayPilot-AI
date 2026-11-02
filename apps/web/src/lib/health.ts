"use client";

// Is the PayPilot API answering? One shared check for the whole app (the header badge and the
// "waking up" banner both read it). Render's free plan puts the API to sleep after ~15 idle
// minutes and the first request takes up to a minute, so we keep retrying until it answers.

import { useSyncExternalStore } from "react";
// Read here, not from ./api, because ./api reports back to this file.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type ApiHealth = {
  status: "checking" | "waking" | "ok" | "down";
  model: string | null; // AI model reading requests, null = backup parser
  since: number; // when we started waiting (ms)
  woke: boolean; // it was asleep and has just answered
};

const SLOW_AFTER_MS = 2000; // show the banner only if the first answer takes longer than this
const DOWN_AFTER_MS = 90_000; // a cold start shouldn't take longer than this

let state: ApiHealth = { status: "checking", model: null, since: 0, woke: false };
const listeners = new Set<() => void>();
let started = false;
let retry: ReturnType<typeof setTimeout> | null = null;

function set(next: Partial<ApiHealth>) {
  state = { ...state, ...next };
  listeners.forEach((l) => l());
}

async function ping(): Promise<{ ai_model?: string | null } | null> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 8000);
  try {
    const r = await fetch(`${API_URL}/health`, { cache: "no-store", signal: ctrl.signal });
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function start() {
  if (started || typeof window === "undefined") return;
  started = true;
  state = { ...state, since: Date.now() };
  const slow = setTimeout(() => state.status === "checking" && set({ status: "waking" }), SLOW_AFTER_MS);

  const attempt = async () => {
    const h = await ping();
    if (h) {
      clearTimeout(slow);
      const wasWaiting = state.status !== "checking";
      set({ status: "ok", model: h.ai_model ?? null, woke: wasWaiting });
      if (wasWaiting) setTimeout(() => set({ woke: false }), 2500);
      return;
    }
    if (state.status === "checking") set({ status: "waking" });
    if (Date.now() - state.since > DOWN_AFTER_MS && state.status !== "down") set({ status: "down" });
    retry = setTimeout(attempt, state.status === "down" ? 5000 : 3000);
  };
  attempt();
}

// Any API call that succeeds proves the server is awake: re-check now instead of waiting for the
// next retry, so the banner and badge never lag behind data that has already loaded.
let rechecking = false;
export function noteApiAlive() {
  if (typeof window === "undefined" || state.status === "ok" || rechecking) return;
  rechecking = true;
  if (retry) clearTimeout(retry);
  ping().then((h) => {
    rechecking = false;
    if (h) {
      const wasWaiting = state.status !== "checking";
      set({ status: "ok", model: h.ai_model ?? null, woke: wasWaiting });
      if (wasWaiting) setTimeout(() => set({ woke: false }), 2500);
    }
  });
}

function subscribe(l: () => void) {
  listeners.add(l);
  start();
  return () => listeners.delete(l);
}

const SERVER: ApiHealth = { status: "checking", model: null, since: 0, woke: false };

export function useApiHealth(): ApiHealth {
  return useSyncExternalStore(subscribe, () => state, () => SERVER);
}
