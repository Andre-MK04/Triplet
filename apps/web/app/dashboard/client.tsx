"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Field, Input, Select } from "../../components/ui/Input";
import { EmptyState, Notice, Spinner } from "../../components/ui/Misc";
import { apiDelete, apiGet, apiPatch, apiPost } from "../../lib/api";
import { airportCity } from "../../lib/airports";
import { formatPrice, timeAgo } from "../../lib/format";

type DashboardSavedSearch = {
  id: string;
  email: string;
  name?: string | null;
  originAirports: string[];
  startDate: string;
  endDate: string;
  minTripLengthDays: number;
  maxTripLengthDays: number;
  maxBudget: number;
  maxGroundTransferHours: number;
  tripStyle: string;
  frequency: string;
  isActive: boolean;
  lastCheckedAt?: string | null;
  lastNotifiedAt?: string | null;
  lastBestPrice?: number | null;
};

type DashboardBilling = {
  plan: string;
  subscriptionStatus: string;
  usage: {
    aiSearchesToday: number;
    aiSearchesPerDay: number;
    activeSavedSearches: number;
    savedSearchLimit: number;
  };
  canUpgrade: boolean;
  canManageBilling: boolean;
};

type DashboardData = {
  user: { email: string; displayName?: string | null };
  billing: DashboardBilling;
  savedSearches: DashboardSavedSearch[];
};

function WatchAction({ label, onClick, disabled, tone = "default" }: { label: string; onClick: () => void; disabled: boolean; tone?: "default" | "danger" }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={
        "font-mono text-[11px] font-semibold uppercase tracking-label transition-colors disabled:opacity-50 " +
        (tone === "danger" ? "text-coral/80 hover:text-coral" : "text-mist hover:text-mint")
      }
    >
      {label}
    </button>
  );
}

function SavedWatchRow({
  search,
  busy,
  onPreview,
  onEdit,
  onToggle,
  onDelete,
}: {
  search: DashboardSavedSearch;
  busy: boolean;
  onPreview: () => void;
  onEdit: () => void;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const checked = timeAgo(search.lastCheckedAt);
  const notified = timeAgo(search.lastNotifiedAt);
  return (
    <article className="border-b border-line py-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-display text-xl font-bold text-cloud">{search.name || "Saved watch"}</h3>
        <span
          className={
            "font-mono text-[10px] font-semibold uppercase tracking-label " +
            (search.isActive ? "text-mint" : "text-coral")
          }
        >
          {search.isActive ? "● Active" : "○ Paused"}
        </span>
      </div>
      <p className="mono-num mt-1.5 font-mono text-xs text-mist">
        {search.originAirports.map(airportCity).join(", ")} · {search.startDate} → {search.endDate} ·{" "}
        {search.minTripLengthDays}–{search.maxTripLengthDays} days · under {formatPrice(search.maxBudget)}
      </p>
      <p className="mono-num mt-1 font-mono text-[10px] uppercase tracking-[0.06em] text-mist/60">
        {search.frequency} checks · checked {checked ?? "never"} · notified {notified ?? "never"} · best{" "}
        {search.lastBestPrice ? formatPrice(search.lastBestPrice) : "not yet"}
      </p>
      <div className="mt-3 flex flex-wrap gap-5">
        <WatchAction label="Preview" onClick={onPreview} disabled={busy} />
        <WatchAction label="Edit" onClick={onEdit} disabled={busy} />
        <WatchAction label={search.isActive ? "Pause" : "Resume"} onClick={onToggle} disabled={busy} />
        <WatchAction label="Delete" onClick={onDelete} disabled={busy} tone="danger" />
      </div>
    </article>
  );
}

export function DashboardClient() {
  const { user, isLoading: authLoading } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [status, setStatus] = useState<{ tone: "info" | "success" | "error"; text: string } | null>(null);
  const [editing, setEditing] = useState<DashboardSavedSearch | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await apiGet<DashboardData>("/me/dashboard"));
      setLoadFailed(false);
    } catch {
      // Never leave the page on an endless spinner — surface the failure.
      setData(null);
      setLoadFailed(true);
    }
  }, []);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  async function withBusy(id: string, action: () => Promise<void>) {
    setBusyId(id);
    setStatus(null);
    try {
      await action();
    } catch (error) {
      setStatus({ tone: "error", text: error instanceof Error ? error.message : "Action failed." });
    } finally {
      setBusyId(null);
    }
  }

  async function preview(id: string) {
    await withBusy(id, async () => {
      const result = await apiPost<{ resultCount?: number; bestPrice?: number | null }>(
        `/me/saved-searches/${id}/run`,
      );
      setStatus({
        tone: "success",
        text: `Preview complete: ${result.resultCount ?? 0} matching trip(s)${
          result.bestPrice ? `, best ${formatPrice(result.bestPrice)}` : ""
        }.`,
      });
      await load();
    });
  }

  async function toggle(search: DashboardSavedSearch) {
    await withBusy(search.id, async () => {
      await apiPost(`/me/saved-searches/${search.id}/${search.isActive ? "pause" : "resume"}`);
      await load();
    });
  }

  async function removeWatch(id: string) {
    await withBusy(id, async () => {
      await apiDelete(`/me/saved-searches/${id}`);
      await load();
    });
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    await withBusy(editing.id, async () => {
      await apiPatch(`/me/saved-searches/${editing.id}`, editing);
      setEditing(null);
      await load();
    });
  }

  async function startCheckout() {
    try {
      const result = await apiPost<{ checkoutUrl: string }>("/billing/create-checkout-session", {
        interval: "monthly",
      });
      window.location.href = result.checkoutUrl;
    } catch {
      setStatus({ tone: "info", text: "Billing is not enabled in this environment." });
    }
  }

  async function manageBilling() {
    try {
      const result = await apiPost<{ portalUrl: string }>("/billing/create-portal-session");
      window.location.href = result.portalUrl;
    } catch {
      setStatus({ tone: "error", text: "Could not open the billing portal." });
    }
  }

  if (authLoading) {
    return (
      <AppShell>
        <div className="flex justify-center py-24"><Spinner /></div>
      </AppShell>
    );
  }

  if (!user) {
    return (
      <AppShell>
        <EmptyState icon="🔐" title="Log in to see your dashboard" action={<ButtonLink href="/login">Log in</ButtonLink>}>
          Your saved watches, usage, and plan live here.
        </EmptyState>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-8 pb-10">
        <header>
          <h1 className="font-display text-3xl font-bold text-cloud sm:text-4xl">
            Welcome back{user.displayName ? `, ${user.displayName}` : ""}.
          </h1>
          {data ? (
            <p className="mt-3 leading-relaxed text-mist">
              Triplet is watching{" "}
              <span className="text-cloud">
                {data.billing.usage.activeSavedSearches} of {data.billing.usage.savedSearchLimit}
              </span>{" "}
              searches for you
              {data.savedSearches.some((s) => s.lastBestPrice != null) ? (
                <>
                  {" "}
                  — best find so far{" "}
                  <span className="mono-num font-mono text-coral">
                    {formatPrice(Math.min(...data.savedSearches.filter((s) => s.lastBestPrice != null).map((s) => s.lastBestPrice!)))}
                  </span>
                </>
              ) : null}
              .
            </p>
          ) : (
            <p className="mt-3 text-mist">Triplet keeps watching while you&apos;re away.</p>
          )}
          {data ? (
            <p className="mono-num mt-2 font-mono text-[10px] uppercase tracking-label text-mist/60">
              {data.billing.plan === "pro" ? "Triplet Pro" : "Free plan"} · {data.billing.subscriptionStatus} · AI
              searches today {data.billing.usage.aiSearchesToday}/{data.billing.usage.aiSearchesPerDay}
            </p>
          ) : null}
        </header>

        {status ? <Notice tone={status.tone === "info" ? "info" : status.tone}>{status.text}</Notice> : null}

        {!data && !loadFailed ? (
          <div className="flex justify-center py-10"><Spinner label="Loading dashboard…" /></div>
        ) : null}

        {!data && loadFailed ? (
          <EmptyState
            title="Couldn't load your dashboard"
            action={
              <Button variant="secondary" onClick={() => void load()}>
                Try again
              </Button>
            }
          >
            The API didn&apos;t respond. Your watches are safe — this is just a loading problem.
          </EmptyState>
        ) : null}

        {data ? (
          <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
            <section>
              <div className="flex items-center justify-between border-b border-line pb-3">
                <h2 className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
                  Your watches
                </h2>
                <ButtonLink href="/discover" variant="secondary" size="sm">+ New watch</ButtonLink>
              </div>
              {data.savedSearches.length === 0 ? (
                <EmptyState
                  title="No watches yet"
                  action={<ButtonLink href="/discover">Run your first search</ButtonLink>}
                >
                  Run a search on the Discover page, then hit “Watch this search” — Triplet will email you
                  when a real deal shows up.
                </EmptyState>
              ) : (
                data.savedSearches.map((search) => (
                  <SavedWatchRow
                    key={search.id}
                    search={search}
                    busy={busyId === search.id}
                    onPreview={() => void preview(search.id)}
                    onEdit={() => setEditing(search)}
                    onToggle={() => void toggle(search)}
                    onDelete={() => void removeWatch(search.id)}
                  />
                ))
              )}
            </section>

            <aside className="space-y-4">
              <Card>
                <h2 className="font-display text-lg font-bold text-cloud">Billing</h2>
                <p className="mt-2 text-sm text-mist">
                  {data.billing.plan === "pro"
                    ? "Manage your subscription and invoices in Stripe."
                    : "Pro unlocks more watches, more AI searches, and weekly digests."}
                </p>
                {data.billing.canManageBilling ? (
                  <Button variant="secondary" className="mt-4 w-full" onClick={() => void manageBilling()}>
                    Manage billing
                  </Button>
                ) : (
                  <Button className="mt-4 w-full" onClick={() => void startCheckout()}>
                    Upgrade to Pro
                  </Button>
                )}
              </Card>
              <Card>
                <h2 className="font-display text-lg font-bold text-cloud">Travel profile</h2>
                <p className="mt-2 text-sm text-mist">
                  Airports, budget, and comfort rules power your alerts and prefill every search.
                </p>
                <ButtonLink href="/onboarding" variant="secondary" className="mt-4 w-full">
                  Edit travel profile
                </ButtonLink>
              </Card>
            </aside>
          </div>
        ) : null}
      </div>

      {editing ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/90 px-4" role="dialog" aria-modal="true" aria-label="Edit watch">
          <form onSubmit={saveEdit} className="w-full max-w-xl space-y-4 border border-line bg-ink-raised p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-display text-xl font-bold text-cloud">Edit watch</h2>
              <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(null)}>✕ Close</Button>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Name">
                <Input value={editing.name ?? ""} onChange={(event) => setEditing({ ...editing, name: event.target.value })} />
              </Field>
              <Field label="Origin airports (comma-separated)">
                <Input
                  value={editing.originAirports.join(", ")}
                  onChange={(event) =>
                    setEditing({
                      ...editing,
                      originAirports: event.target.value
                        .split(",")
                        .map((code) => code.trim().toUpperCase())
                        .filter(Boolean),
                    })
                  }
                />
              </Field>
              <Field label="Start date">
                <Input type="date" value={editing.startDate} onChange={(event) => setEditing({ ...editing, startDate: event.target.value })} />
              </Field>
              <Field label="End date">
                <Input type="date" value={editing.endDate} onChange={(event) => setEditing({ ...editing, endDate: event.target.value })} />
              </Field>
              <Field label="Max budget (€)">
                <Input type="number" value={editing.maxBudget} onChange={(event) => setEditing({ ...editing, maxBudget: Number(event.target.value) })} />
              </Field>
              <Field label="Frequency" hint="Weekly digests are a Pro feature.">
                <Select value={editing.frequency} onChange={(event) => setEditing({ ...editing, frequency: event.target.value })}>
                  <option value="daily">daily</option>
                  <option value="weekly">weekly</option>
                </Select>
              </Field>
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setEditing(null)}>Cancel</Button>
              <Button type="submit" disabled={busyId === editing.id}>Save changes</Button>
            </div>
          </form>
        </div>
      ) : null}
    </AppShell>
  );
}
