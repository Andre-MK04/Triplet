"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Badge } from "../../components/ui/Badge";
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

function UsageCard({ label, value, max, detail }: { label: string; value: number; max: number; detail?: string }) {
  const percent = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <Card>
      <p className="text-xs font-semibold uppercase tracking-wide text-mist">{label}</p>
      <p className="mt-1 font-display text-2xl font-bold text-cloud">
        {value} <span className="text-base font-medium text-mist">/ {max}</span>
      </p>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
        <div
          className={`h-full rounded-full ${percent >= 100 ? "bg-coral" : "bg-gradient-to-r from-mint to-sky"}`}
          style={{ width: `${percent}%` }}
        />
      </div>
      {detail ? <p className="mt-2 text-xs text-mist/70">{detail}</p> : null}
    </Card>
  );
}

function SavedWatchCard({
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
    <Card as="article" className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="truncate font-display text-lg font-bold text-cloud">{search.name || "Saved watch"}</h3>
          <p className="mt-0.5 text-sm text-mist">
            {search.originAirports.map(airportCity).join(", ")} · {search.startDate} → {search.endDate} ·{" "}
            {search.minTripLengthDays}–{search.maxTripLengthDays} days · under {formatPrice(search.maxBudget)}
          </p>
        </div>
        <Badge tone={search.isActive ? "mint" : "coral"}>{search.isActive ? "active" : "paused"}</Badge>
      </div>
      <p className="text-xs text-mist/70">
        {search.frequency} checks · last checked {checked ?? "never"} · last notified {notified ?? "never"} · best
        price {search.lastBestPrice ? formatPrice(search.lastBestPrice) : "not yet"}
      </p>
      <div className="flex flex-wrap gap-2 border-t border-dashed border-line pt-3">
        <Button size="sm" onClick={onPreview} disabled={busy}>Preview results</Button>
        <Button size="sm" variant="secondary" onClick={onEdit} disabled={busy}>Edit</Button>
        <Button size="sm" variant="secondary" onClick={onToggle} disabled={busy}>
          {search.isActive ? "Pause" : "Resume"}
        </Button>
        <Button size="sm" variant="danger" onClick={onDelete} disabled={busy}>Delete</Button>
      </div>
    </Card>
  );
}

export function DashboardClient() {
  const { user, isLoading: authLoading } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [status, setStatus] = useState<{ tone: "info" | "success" | "error"; text: string } | null>(null);
  const [editing, setEditing] = useState<DashboardSavedSearch | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setData(await apiGet<DashboardData>("/me/dashboard"));
    } catch {
      setData(null);
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
          <h1 className="font-display text-3xl font-bold text-cloud">
            Welcome back{user.displayName ? `, ${user.displayName}` : ""} 👋
          </h1>
          <p className="mt-1 text-mist">Triplet keeps watching while you're away.</p>
        </header>

        {status ? <Notice tone={status.tone === "info" ? "info" : status.tone}>{status.text}</Notice> : null}

        {data ? (
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <p className="text-xs font-semibold uppercase tracking-wide text-mist">Plan</p>
              <p className="mt-1 font-display text-2xl font-bold text-cloud">
                {data.billing.plan === "pro" ? "Triplet Pro" : "Free"}
              </p>
              <p className="mt-1 text-xs text-mint">{data.billing.subscriptionStatus}</p>
            </Card>
            <UsageCard
              label="Saved watches"
              value={data.billing.usage.activeSavedSearches}
              max={data.billing.usage.savedSearchLimit}
            />
            <UsageCard
              label="AI searches today"
              value={data.billing.usage.aiSearchesToday}
              max={data.billing.usage.aiSearchesPerDay}
              detail="Resets daily"
            />
          </div>
        ) : (
          <div className="flex justify-center py-10"><Spinner label="Loading dashboard…" /></div>
        )}

        {data ? (
          <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h2 className="font-display text-xl font-bold text-cloud">Saved watches</h2>
                <ButtonLink href="/discover" variant="secondary" size="sm">+ New watch</ButtonLink>
              </div>
              {data.savedSearches.length === 0 ? (
                <EmptyState
                  icon="🔭"
                  title="No watches yet"
                  action={<ButtonLink href="/discover">Run your first search</ButtonLink>}
                >
                  Run a search on the Discover page, then hit “Watch this search” — Triplet will email you
                  when a real deal shows up.
                </EmptyState>
              ) : (
                data.savedSearches.map((search) => (
                  <SavedWatchCard
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
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/80 px-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-label="Edit watch">
          <form onSubmit={saveEdit} className="glass rounded-card w-full max-w-xl space-y-4 p-6 shadow-lift">
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
