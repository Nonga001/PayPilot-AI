"use client";

import { BookUser, Loader2, Mail, PencilLine, Plus, ShieldCheck, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Shell } from "@/components/shell";
import { api, type Payee } from "@/lib/api";
import { initials } from "@/lib/format";

const CURRENCIES = ["USD", "EUR", "GBP", "CAD", "AUD"];
const EMPTY = { name: "", paypal_email: "", country: "", default_currency: "USD" };

export default function PayeesPage() {
  const [payees, setPayees] = useState<Payee[] | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [editing, setEditing] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      setPayees((await api.payees()).payees);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  useEffect(() => {
    let live = true;
    api
      .payees()
      .then((r) => live && setPayees(r.payees))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.savePayee({
        name: form.name.trim(),
        paypal_email: form.paypal_email.trim() || null,
        country: form.country.trim().toUpperCase() || null,
        default_currency: form.default_currency || null,
      });
      setForm(EMPTY);
      setEditing(null);
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      await api.deletePayee(id);
      setConfirmDelete(null);
      await load();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <Shell>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-[minmax(0,1fr)_360px] lg:gap-10">
        <section>
          <h1 className="font-display text-3xl font-semibold tracking-tight">Payees</h1>
          <p className="mt-1 max-w-xl text-[15px] text-muted">
            Saved suppliers and clients. PayPilot pays saved payees by PayPal Payouts; anyone new is flagged for review the
            first time.
          </p>

          {payees === null ? (
            <div className="grid h-40 place-items-center">
              <Loader2 className="size-6 animate-spin text-ai" aria-label="Loading payees" />
            </div>
          ) : payees.length === 0 ? (
            <p className="mt-8 text-muted">No payees yet. Add your first supplier on the right.</p>
          ) : (
            <ul className="mt-6 divide-y divide-line rounded-2xl bg-panel ring-1 ring-line">
              {payees.map((p) => (
                <li key={p.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
                  <span className="grid size-10 shrink-0 place-items-center rounded-full bg-ai-soft font-display font-semibold text-ai">
                    {initials(p.name)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-medium">{p.name}</div>
                    <div className="flex flex-wrap items-center gap-x-3 text-sm text-muted">
                      <span className="inline-flex items-center gap-1">
                        <Mail className="size-3.5" aria-hidden />
                        {p.paypal_email || "No PayPal email"}
                      </span>
                      {p.country && <span>{p.country}</span>}
                      {p.default_currency && <span>{p.default_currency}</span>}
                    </div>
                  </div>
                  {confirmDelete === p.id ? (
                    <span className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => remove(p.id)}
                        className="rounded-lg bg-bad px-3 py-1.5 text-sm font-semibold text-white"
                      >
                        Remove {p.name}
                      </button>
                      <button type="button" onClick={() => setConfirmDelete(null)} className="p-1.5 text-muted hover:text-ink" aria-label="Keep payee">
                        <X className="size-4" />
                      </button>
                    </span>
                  ) : (
                    <span className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => {
                          setEditing(p.id);
                          setForm({
                            name: p.name,
                            paypal_email: p.paypal_email ?? "",
                            country: p.country ?? "",
                            default_currency: p.default_currency ?? "USD",
                          });
                        }}
                        className="rounded-lg p-2 text-muted hover:bg-cloud hover:text-ink"
                        aria-label={`Edit ${p.name}`}
                      >
                        <PencilLine className="size-4" />
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDelete(p.id)}
                        className="rounded-lg p-2 text-muted hover:bg-bad-soft hover:text-bad"
                        aria-label={`Remove ${p.name}`}
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="lg:pt-12">
          <form onSubmit={save} className="rounded-2xl bg-panel p-5 ring-1 ring-line">
            <h2 className="flex items-center gap-2 font-display text-lg font-semibold">
              <BookUser className="size-4 text-muted" aria-hidden />
              {editing ? "Edit payee" : "Add a payee"}
            </h2>
            <div className="mt-4 space-y-3">
              {(
                [
                  ["name", "Name", "Acme Supplies", "text"],
                  ["paypal_email", "PayPal email", "billing@acme.example.com", "email"],
                  ["country", "Country code", "KE", "text"],
                ] as const
              ).map(([key, label, ph, type]) => (
                <label key={key} className="block">
                  <span className="text-sm text-muted">{label}</span>
                  <input
                    type={type}
                    required={key === "name"}
                    maxLength={key === "country" ? 2 : 120}
                    value={form[key]}
                    onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                    placeholder={ph}
                    className="mt-1 block w-full rounded-xl bg-cloud/60 px-3 py-2 text-[15px] ring-1 ring-line placeholder:text-faint focus:outline-none focus:ring-2 focus:ring-ai"
                  />
                </label>
              ))}
              <label className="block">
                <span className="text-sm text-muted">Usual currency</span>
                <select
                  value={form.default_currency}
                  onChange={(e) => setForm({ ...form, default_currency: e.target.value })}
                  className="mt-1 block w-full rounded-xl bg-cloud/60 px-3 py-2 text-[15px] ring-1 ring-line focus:outline-none focus:ring-2 focus:ring-ai"
                >
                  {CURRENCIES.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
            </div>
            {error && <p className="mt-3 text-sm text-bad">{error}</p>}
            <div className="mt-5 flex items-center gap-3">
              <button
                type="submit"
                disabled={saving || !form.name.trim()}
                className="inline-flex items-center gap-2 rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {saving ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Plus className="size-4" aria-hidden />}
                {editing ? "Save changes" : "Add payee"}
              </button>
              {editing && (
                <button
                  type="button"
                  onClick={() => {
                    setEditing(null);
                    setForm(EMPTY);
                  }}
                  className="text-sm font-medium text-muted hover:text-ink"
                >
                  Cancel
                </button>
              )}
            </div>
            <p className="mt-4 flex items-start gap-2 text-xs text-faint">
              <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden />
              Every change is written to the audit trail. Swapping a supplier&apos;s payment email is a common fraud
              trick, so the old email is recorded too.
            </p>
            <p className="mt-2 text-xs text-faint">
              For real sandbox deliveries, use personal accounts from developer.paypal.com, Testing Tools, Sandbox Accounts.
            </p>
          </form>
        </aside>
      </div>
    </Shell>
  );
}
