"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Field, Input, Select } from "../../components/ui/Input";
import { EmptyState, Notice, Spinner } from "../../components/ui/Misc";
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from "../../lib/api";
import { WATCH_TRIGGERS, triggerHint, type WatchTriggerMode } from "../../lib/watchTriggers";
import { airportCity } from "../../lib/airports";
import { formatPrice, timeAgo } from "../../lib/format";
import type { TravelProfile } from "../../lib/types";

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
  directOnly?: boolean | null;
  includeBaggage?: boolean | null;
  frequency: string;
  triggerMode?: string | null;
  isActive: boolean;
  lastCheckedAt?: string | null;
  lastNotifiedAt?: string | null;
  lastBestPrice?: number | null;
};

type WatchInsights = {
  savedSearchId: string;
  alertTriggerMode: string;
  totalChecks: number;
  successfulChecks: number;
  notificationCount: number;
  currentBestPrice?: number | null;
  lowestObservedPrice?: number | null;
  averageObservedPrice?: number | null;
  changeFromPrevious?: number | null;
  budgetHeadroom?: number | null;
  history: Array<{
    checkedAt: string;
    bestPrice?: number | null;
    resultCount: number;
    status: string;
  }>;
  deliveries: Array<{
    sentAt: string;
    status: string;
    provider: string;
    subject: string;
  }>;
};

type DashboardBilling = {
  plan: "free" | "trial" | "pro" | "owner";
  subscriptionStatus: string;
  trialDaysRemaining: number;
  usage: {
    aiSearchesThisMonth: number;
    aiSearchesPerMonth: number;
    activeSavedSearches: number;
    savedSearchLimit: number;
    maxOriginAirports: number;
    dailyWatchChecks: boolean;
    unlimited?: boolean;
  };
  canStartTrial: boolean;
  canUpgrade: boolean;
  canManageBilling: boolean;
};

const PLAN_LABEL: Record<string, string> = {
  free: "Free",
  trial: "Triplet Pro trial",
  pro: "Triplet Pro",
  owner: "Triplet Owner",
};

type DashboardData = {
  user: { email: string; displayName?: string | null };
  billing: DashboardBilling;
  savedSearches: DashboardSavedSearch[];
  travelProfile: TravelProfile;
};

const TRIGGER_LABELS: Record<string, string> = {
  any: "Any worthwhile deal",
  below_budget: "Anything below my budget",
  route_deal: "Only unusually cheap routes",
  price_drop: "Only meaningful price drops",
};

function PriceHistoryChart({ insights, budget }: { insights: WatchInsights; budget: number }) {
  const points = useMemo(
    () => insights.history.filter((point) => point.bestPrice != null) as Array<WatchInsights["history"][number] & { bestPrice: number }>,
    [insights.history],
  );

  if (points.length === 0) {
    return (
      <div className="grid h-44 place-items-center border-y border-line">
        <p className="max-w-sm text-center text-sm text-mist">
          No price history yet. Run the watch once to establish its first baseline.
        </p>
      </div>
    );
  }

  const width = 640;
  const height = 176;
  const padX = 22;
  const padY = 20;
  const values = [...points.map((point) => point.bestPrice), budget];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(max - min, 20);
  const low = min - spread * 0.15;
  const high = max + spread * 0.15;
  const x = (index: number) => padX + (index / Math.max(points.length - 1, 1)) * (width - padX * 2);
  const y = (price: number) => padY + ((high - price) / (high - low)) * (height - padY * 2);
  const path = points.map((point, index) => `${x(index)},${y(point.bestPrice)}`).join(" ");

  return (
    <div className="relative h-44 w-full border-y border-line" aria-label="Watch price history chart">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full" role="img">
        <title>Best observed prices over the last {points.length} checks</title>
        <line
          x1={padX}
          x2={width - padX}
          y1={y(budget)}
          y2={y(budget)}
          stroke="currentColor"
          className="text-coral/50"
          strokeDasharray="5 5"
        />
        <text x={width - padX} y={Math.max(12, y(budget) - 6)} textAnchor="end" className="fill-coral font-mono text-[10px]">
          BUDGET {formatPrice(budget)}
        </text>
        {points.length > 1 ? (
          <polyline points={path} fill="none" stroke="currentColor" strokeWidth="2" className="text-mint" vectorEffect="non-scaling-stroke" />
        ) : null}
        {points.map((point, index) => (
          <g key={`${point.checkedAt}-${index}`}>
            <circle cx={x(index)} cy={y(point.bestPrice)} r={points.length === 1 ? 5 : 3.5} className="fill-mint" />
            {(index === 0 || index === points.length - 1) ? (
              <text
                x={x(index)}
                y={Math.max(12, y(point.bestPrice) - 9)}
                textAnchor={index === 0 ? "start" : "end"}
                className="fill-cloud font-mono text-[10px]"
              >
                {formatPrice(point.bestPrice)}
              </text>
            ) : null}
          </g>
        ))}
      </svg>
    </div>
  );
}

function WatchInsightsPanel({ insights, search }: { insights: WatchInsights; search: DashboardSavedSearch }) {
  const change = insights.changeFromPrevious;
  return (
    <div className="mt-5 border-l-2 border-mint/50 pl-4 sm:pl-5">
      <div className="grid gap-px bg-line sm:grid-cols-4">
        {[
          ["Current", insights.currentBestPrice != null ? formatPrice(insights.currentBestPrice) : "—"],
          ["Observed low", insights.lowestObservedPrice != null ? formatPrice(insights.lowestObservedPrice) : "—"],
          ["Average", insights.averageObservedPrice != null ? formatPrice(insights.averageObservedPrice) : "—"],
          [
            "Latest move",
            change == null ? "—" : change === 0 ? "No change" : `${formatPrice(Math.abs(change))} ${change < 0 ? "lower" : "higher"}`,
          ],
        ].map(([label, value]) => (
          <div key={label} className="bg-ink-raised px-3 py-3">
            <p className="font-mono text-[11px] uppercase tracking-label text-mist-dim">{label}</p>
            <p className="mono-num mt-1 font-mono text-sm font-semibold text-cloud">{value}</p>
          </div>
        ))}
      </div>

      <div className="mt-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-label text-mist">Price history</p>
          <p className="font-mono text-[10px] uppercase tracking-label text-mist-dim">
            {insights.totalChecks} checks · {insights.notificationCount} alerts · {TRIGGER_LABELS[insights.alertTriggerMode] ?? insights.alertTriggerMode}
          </p>
        </div>
        <PriceHistoryChart insights={insights} budget={search.maxBudget} />
      </div>

      <div className="mt-5">
        <p className="font-mono text-[10px] font-semibold uppercase tracking-label text-mist">Recent delivery</p>
        {insights.deliveries.length ? (
          <div className="mt-2 divide-y divide-line border-t border-line">
            {insights.deliveries.slice(0, 4).map((delivery) => (
              <div key={`${delivery.sentAt}-${delivery.subject}`} className="grid gap-1 py-2.5 sm:grid-cols-[5rem_1fr_auto] sm:items-center sm:gap-3">
                <span className={`font-mono text-[11px] uppercase tracking-label ${delivery.status === "sent" ? "text-mint" : "text-coral"}`}>
                  {delivery.status}
                </span>
                <span className="truncate text-xs text-cloud">{delivery.subject}</span>
                <span className="font-mono text-[11px] uppercase tracking-label text-mist-dim">{timeAgo(delivery.sentAt)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-2 text-sm text-mist">No alert has been sent for this watch yet.</p>
        )}
      </div>
    </div>
  );
}

function UsageMeter({
  label,
  used,
  limit,
  unlimited = false,
}: {
  label: string;
  used: number;
  limit: number;
  unlimited?: boolean;
}) {
  const pct = unlimited ? 0 : limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;
  return (
    <div className="bg-ink-raised px-5 py-4">
      <p className="font-mono text-[10px] uppercase tracking-label text-mist">{label}</p>
      <p className="mono-num mt-1 font-display text-2xl font-bold text-cloud">
        {used}
        <span className="text-base font-normal text-mist"> / {unlimited ? "∞" : limit}</span>
      </p>
      <div className="mt-3 h-0.5 w-full bg-line">
        <div className={"h-full " + (pct >= 100 ? "bg-coral" : "bg-mint")} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function PlanTile({ billing, onManage }: { billing: DashboardBilling; onManage: () => void }) {
  return (
    <div className="flex flex-col justify-between bg-ink-raised px-5 py-4">
      <div>
        <p className="font-mono text-[10px] uppercase tracking-label text-mist">Plan</p>
        <p className="mt-1 font-display text-2xl font-bold text-cloud">{PLAN_LABEL[billing.plan] ?? "Free"}</p>
      </div>
      <div className="mt-3">
        {billing.plan === "owner" ? (
          <span className="font-mono text-[11px] uppercase tracking-label text-mist">
            All limits lifted
          </span>
        ) : billing.plan === "pro" ? (
          <button
            type="button"
            onClick={onManage}
            className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist transition-colors hover:text-mint"
          >
            Manage billing →
          </button>
        ) : billing.plan === "trial" ? (
          <a
            href="/pricing"
            className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint transition-colors hover:text-cloud"
          >
            {billing.trialDaysRemaining} days left — keep Pro →
          </a>
        ) : (
          <a
            href="/pricing"
            className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint transition-colors hover:text-cloud"
          >
            Upgrade for daily checks →
          </a>
        )}
      </div>
    </div>
  );
}

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
  expanded,
  insights,
  insightsLoading,
  onCheck,
  onDetails,
  onEdit,
  onToggle,
  onDelete,
}: {
  search: DashboardSavedSearch;
  busy: boolean;
  expanded: boolean;
  insights?: WatchInsights;
  insightsLoading: boolean;
  onCheck: () => void;
  onDetails: () => void;
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
      {/* When a watch last ran and what it found is the whole point of the
          row, so it is read at label size rather than shrunk below it. */}
      <p className="mono-num mt-1 font-mono text-[11px] uppercase leading-relaxed tracking-[0.06em] text-mist-dim">
        {search.frequency} checks · checked {checked ?? "never"} · notified {notified ?? "never"} · best{" "}
        {search.lastBestPrice ? formatPrice(search.lastBestPrice) : "not yet"}
      </p>
      <div className="mt-3 flex flex-wrap gap-5">
        <WatchAction label={expanded ? "Hide details" : "Details"} onClick={onDetails} disabled={busy} />
        <WatchAction label="Check now" onClick={onCheck} disabled={busy} />
        <WatchAction label="Edit" onClick={onEdit} disabled={busy} />
        <WatchAction label={search.isActive ? "Pause" : "Resume"} onClick={onToggle} disabled={busy} />
        <WatchAction label="Delete" onClick={onDelete} disabled={busy} tone="danger" />
      </div>
      {expanded && insightsLoading ? <div className="mt-5"><Spinner label="Loading watch history…" /></div> : null}
      {expanded && insights ? <WatchInsightsPanel insights={insights} search={search} /> : null}
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
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [insights, setInsights] = useState<Record<string, WatchInsights>>({});
  const [insightsLoadingId, setInsightsLoadingId] = useState<string | null>(null);
  const [profileSaving, setProfileSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const [dashboard, travelProfile] = await Promise.all([
        apiGet<Omit<DashboardData, "travelProfile">>("/me/dashboard"),
        apiGet<TravelProfile>("/me/travel-profile"),
      ]);
      setData({ ...dashboard, travelProfile });
      setLoadFailed(false);
    } catch {
      // Never leave the page on an endless spinner — surface the failure.
      setData(null);
      setLoadFailed(true);
    }
  }, []);

  async function loadInsights(id: string, force = false) {
    if (!force && insights[id]) return;
    setInsightsLoadingId(id);
    try {
      const result = await apiGet<WatchInsights>(`/me/saved-searches/${id}/insights`);
      setInsights((current) => ({ ...current, [id]: result }));
    } catch (error) {
      setStatus({ tone: "error", text: error instanceof Error ? error.message : "Could not load watch history." });
    } finally {
      setInsightsLoadingId(null);
    }
  }

  async function toggleDetails(id: string) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    await loadInsights(id);
  }

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

  async function checkNow(id: string) {
    await withBusy(id, async () => {
      const result = await apiPost<{ resultCount?: number; bestPrice?: number | null; notificationSent?: boolean }>(
        `/me/saved-searches/${id}/run`,
      );
      setStatus({
        tone: "success",
        text: `Watch checked: ${result.resultCount ?? 0} matching trip(s)${
          result.bestPrice ? `, best ${formatPrice(result.bestPrice)}` : ""
        }${result.notificationSent ? ". Alert sent." : "."}`,
      });
      await load();
      await loadInsights(id, true);
    });
  }

  async function saveProfilePreferences() {
    if (!data) return;
    setProfileSaving(true);
    setStatus(null);
    try {
      const { userId, isComplete, createdAt, updatedAt, ...payload } = data.travelProfile;
      const saved = await apiPut<TravelProfile>("/me/travel-profile", payload);
      setData({ ...data, travelProfile: saved });
      setInsights({});
      setStatus({ tone: "success", text: "Alert preferences saved." });
    } catch (error) {
      setStatus({ tone: "error", text: error instanceof Error ? error.message : "Could not save alert preferences." });
    } finally {
      setProfileSaving(false);
    }
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
                {data.billing.usage.activeSavedSearches}
                {data.billing.usage.unlimited ? "" : ` of ${data.billing.usage.savedSearchLimit}`}
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
            <p className="mono-num mt-2 font-mono text-[10px] uppercase tracking-label text-mist-dim">
              {PLAN_LABEL[data.billing.plan] ?? "Free plan"}
              {data.billing.plan === "trial" ? ` · ${data.billing.trialDaysRemaining} days left` : ""} · AI searches
              this month {data.billing.usage.aiSearchesThisMonth}
              {data.billing.usage.unlimited ? " (unlimited)" : `/${data.billing.usage.aiSearchesPerMonth}`} ·{" "}
              {data.billing.usage.dailyWatchChecks ? "daily" : "weekly"} checks
            </p>
          ) : null}
        </header>

        {data ? (
          <div className="grid gap-px border border-line bg-line sm:grid-cols-3">
            <UsageMeter
              label="AI searches / month"
              used={data.billing.usage.aiSearchesThisMonth}
              limit={data.billing.usage.aiSearchesPerMonth}
              unlimited={data.billing.usage.unlimited}
            />
            <UsageMeter
              label="Saved watches"
              used={data.billing.usage.activeSavedSearches}
              limit={data.billing.usage.savedSearchLimit}
              unlimited={data.billing.usage.unlimited}
            />
            <PlanTile billing={data.billing} onManage={() => void manageBilling()} />
          </div>
        ) : null}

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
                    expanded={expandedId === search.id}
                    insights={insights[search.id]}
                    insightsLoading={insightsLoadingId === search.id}
                    onCheck={() => void checkNow(search.id)}
                    onDetails={() => void toggleDetails(search.id)}
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
                {data.travelProfile.isComplete ? (
                  <>
                    <p className="mt-2 text-sm text-mist">{data.travelProfile.homeLocation || "Home base not set"}</p>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {data.travelProfile.originAirports.map((code) => (
                        <span key={code} className="border border-line px-2 py-1 font-mono text-[10px] uppercase tracking-label text-cloud">
                          {code}
                        </span>
                      ))}
                    </div>
                  </>
                ) : (
                  <Notice tone="warning">Finish your profile so every search starts with the right home airports.</Notice>
                )}
                <ButtonLink href="/onboarding" variant="secondary" className="mt-4 w-full">
                  {data.travelProfile.isComplete ? "Edit travel profile" : "Finish setup"}
                </ButtonLink>
              </Card>
              <Card>
                <h2 className="font-display text-lg font-bold text-cloud">Alert rules</h2>
                <p className="mt-2 text-sm text-mist">Choose what deserves an email. The rule applies to all active watches.</p>
                <div className="mt-4 space-y-4">
                  <Field label="Notify me for">
                    <Select
                      value={data.travelProfile.alertTriggerMode ?? "any"}
                      onChange={(event) =>
                        setData({
                          ...data,
                          travelProfile: {
                            ...data.travelProfile,
                            alertTriggerMode: event.target.value as TravelProfile["alertTriggerMode"],
                          },
                        })
                      }
                    >
                      <option value="any">Any worthwhile deal</option>
                      <option value="below_budget">Anything below my budget</option>
                      <option value="route_deal">Only unusually cheap routes</option>
                      <option value="price_drop">Only meaningful price drops</option>
                    </Select>
                  </Field>
                  <div className="border-y border-line py-3">
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-[10px] uppercase tracking-label text-mist">Email</span>
                      <span className="font-mono text-[10px] uppercase tracking-label text-mint">Active</span>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-3">
                      <span className="font-mono text-[10px] uppercase tracking-label text-mist">Push</span>
                      <span className="font-mono text-[10px] uppercase tracking-label text-mist-dim">Planned for iOS</span>
                    </div>
                  </div>
                  <Button
                    variant="secondary"
                    className="w-full"
                    disabled={profileSaving || !data.travelProfile.isComplete}
                    onClick={() => void saveProfilePreferences()}
                  >
                    {profileSaving ? "Saving…" : "Save alert rules"}
                  </Button>
                </div>
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
              {/* What is worth an email, kept separate from how often Triplet
                  looks — changing one should not silently change the other. */}
              <Field label="Tell me when" hint={triggerHint((editing.triggerMode ?? "any") as WatchTriggerMode)}>
                <Select
                  value={editing.triggerMode ?? "any"}
                  onChange={(event) => setEditing({ ...editing, triggerMode: event.target.value })}
                >
                  {WATCH_TRIGGERS.map((trigger) => (
                    <option key={trigger.value} value={trigger.value}>
                      {trigger.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Check" hint="Weekly digests are a Pro feature.">
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
