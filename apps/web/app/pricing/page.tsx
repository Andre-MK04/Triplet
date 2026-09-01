"use client";

import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Notice } from "../../components/ui/Misc";
import { ApiError, apiGet, apiPost } from "../../lib/api";

type BillingPlan = {
  plan: string;
  name: string;
  priceLabel: string;
  priceYearlyLabel?: string | null;
  features: string[];
  limits: Record<string, unknown>;
};

/** What GET /billing/plans returns. Everything the page needs, so it invents none. */
type PlansResponse = {
  plans: BillingPlan[];
  billingEnabled: boolean;
  /** Only present when the API calculated it from the configured prices. */
  yearlySavingsPercent?: number | null;
  trialDurationDays: number;
};

type BillingStatus = {
  plan: "free" | "trial" | "pro";
  trialDaysRemaining: number;
  canStartTrial: boolean;
  canManageBilling: boolean;
};

const FAQ = [
  {
    q: "Are prices guaranteed?",
    a: "No. Triplet shows observed or cached fare opportunities. Final prices must always be checked with the provider.",
  },
  {
    q: "Does Triplet book flights?",
    a: "No. Triplet helps you discover and monitor trips. Booking happens with the airline or travel provider.",
  },
  {
    q: "Why is there a limit on AI searches?",
    a: "AI searches and flight checks cost money to run, so limits keep the product sustainable.",
  },
  {
    q: "What happens after the free trial?",
    a: "You return to the Free plan unless you upgrade to Pro.",
  },
  {
    q: "Can I cancel Pro?",
    a: "Yes, billing is managed through Stripe when billing is enabled.",
  },
];

export default function PricingPage() {
  const { user, refresh } = useAuth();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [interval, setBillingInterval] = useState<"monthly" | "yearly">("monthly");
  const [status, setStatus] = useState<{ tone: "info" | "success" | "error"; text: string } | null>(null);
  // Whether checkout can actually complete. Assume it cannot until the API
  // says otherwise, so a slow response never shows a buy button that fails.
  const [billingEnabled, setBillingEnabled] = useState(false);
  // Only set when the API calculated it from the real prices.
  const [yearlySavings, setYearlySavings] = useState<number | null>(null);
  const [trialDurationDays, setTrialDurationDays] = useState<number | null>(null);

  useEffect(() => {
    apiGet<PlansResponse>("/billing/plans")
      .then((data) => {
        setPlans(data.plans);
        setBillingEnabled(data.billingEnabled);
        setYearlySavings(data.yearlySavingsPercent ?? null);
        setTrialDurationDays(data.trialDurationDays);
      })
      .catch(() => setStatus({ tone: "error", text: "Could not load plans. Is the API running?" }));
  }, []);

  const loadBilling = () => {
    if (!user) {
      setBilling(null);
      return;
    }
    apiGet<BillingStatus>("/billing/status").then(setBilling).catch(() => setBilling(null));
  };
  useEffect(loadBilling, [user]);

  async function upgrade() {
    if (!user) {
      window.location.href = "/login";
      return;
    }
    setStatus(null);
    try {
      const data = await apiPost<{ checkoutUrl: string }>("/billing/create-checkout-session", { interval });
      window.location.href = data.checkoutUrl;
    } catch {
      setStatus({ tone: "info", text: "Billing isn't enabled in this environment yet." });
    }
  }

  async function manageBilling() {
    setStatus(null);
    try {
      const data = await apiPost<{ portalUrl: string }>("/billing/create-portal-session");
      window.location.href = data.portalUrl;
    } catch {
      setStatus({ tone: "error", text: "Could not open the billing portal." });
    }
  }

  async function startTrial() {
    setStatus(null);
    try {
      await apiPost("/billing/start-trial");
      await refresh();
      loadBilling();
      setStatus({ tone: "success", text: `Your ${trialDays}-day Triplet Pro trial is active. Enjoy!` });
    } catch (error) {
      const message =
        error instanceof ApiError ? error.message : "Could not start your trial. Please try again.";
      setStatus({ tone: "error", text: message });
    }
  }

  const free = plans.find((plan) => plan.plan === "free");
  const pro = plans.find((plan) => plan.plan === "pro");
  const trialPlan = plans.find((plan) => plan.plan === "trial");

  /**
   * The Free/Pro table, built from the limits each plan actually grants.
   *
   * It used to be a hand-written constant that happened to agree with the
   * backend. Deriving it means a limit change shows up here instead of quietly
   * making this table wrong.
   */
  const comparisonRows = useMemo(() => {
    const limitOf = (plan: BillingPlan | undefined, key: string) => {
      const value = plan?.limits?.[key];
      return typeof value === "number" ? String(value) : "—";
    };
    const cadence = (plan: BillingPlan | undefined) => {
      const allowed = plan?.limits?.allowedAlertFrequencies;
      if (!Array.isArray(allowed)) return "—";
      return allowed.includes("daily") ? "Daily" : "Weekly";
    };
    const yesNo = (plan: BillingPlan | undefined, key: string) =>
      plan?.limits?.[key] ? "Yes" : "—";

    return [
      { label: "AI searches", free: `${limitOf(free, "aiSearchesPerMonth")} / month`,
        pro: `${limitOf(pro, "aiSearchesPerMonth")} / month` },
      { label: "Saved watches", free: limitOf(free, "savedSearchLimit"),
        pro: limitOf(pro, "savedSearchLimit") },
      { label: "Origin airports", free: limitOf(free, "maxOriginAirports"),
        pro: limitOf(pro, "maxOriginAirports") },
      { label: "Fare checks", free: cadence(free), pro: cadence(pro) },
      { label: "Open-jaw and multi-city", free: yesNo(free, "liveProviderAccess"),
        pro: yesNo(pro, "liveProviderAccess") },
      { label: "Priority alerts", free: yesNo(free, "priorityAlerts"),
        pro: yesNo(pro, "priorityAlerts") },
    ];
  }, [free, pro]);

  const trialDays = trialDurationDays ?? 7;
  const proPrice =
    interval === "yearly" ? pro?.priceYearlyLabel ?? pro?.priceLabel ?? "€49/year" : pro?.priceLabel ?? "€6.99/month";

  // Checkout cannot complete without Stripe configured. Offering an upgrade
  // that ends in an error wastes the traveller's intent and looks broken; the
  // honest version says the plan is not ready to buy yet.
  const proCta = !billingEnabled ? (
    <div className="mt-8">
      <Button variant="secondary" className="w-full" disabled>
        Pro · coming soon
      </Button>
      <p className="mt-2 text-center text-xs leading-relaxed text-mist/70">
        Paid plans are not open yet. Everything below is free to use in the meantime.
      </p>
    </div>
  ) : !user ? (
    <ButtonLink href="/login" className="mt-8 w-full">
      Log in to upgrade
    </ButtonLink>
  ) : billing?.plan === "pro" ? (
    <Button variant="secondary" className="mt-8 w-full" onClick={() => void manageBilling()}>
      Manage billing
    </Button>
  ) : billing?.plan === "trial" ? (
    <Button className="mt-8 w-full" onClick={() => void upgrade()}>
      Upgrade before trial ends
    </Button>
  ) : (
    <Button className="mt-8 w-full" onClick={() => void upgrade()}>
      Upgrade to Pro
    </Button>
  );

  const trialCta = () => {
    if (!user) {
      return (
        <ButtonLink href="/signup" variant="secondary">
          Create account to start trial
        </ButtonLink>
      );
    }
    if (billing?.plan === "pro") {
      return <span className="font-mono text-[11px] uppercase tracking-label text-mint">You already have Pro</span>;
    }
    if (billing?.plan === "trial") {
      return (
        <span className="font-mono text-[11px] uppercase tracking-label text-mint">
          Trial active — {billing.trialDaysRemaining} day{billing.trialDaysRemaining === 1 ? "" : "s"} left
        </span>
      );
    }
    if (billing && !billing.canStartTrial) {
      return <span className="font-mono text-[11px] uppercase tracking-label text-mist">Trial already used</span>;
    }
    // The trial needs no card and no Stripe, so it stays available even when
    // paid checkout does not.
    return <Button onClick={() => void startTrial()}>Start {trialDays}-day trial</Button>;
  };

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-14 pb-16">
        <header>
          <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">Pricing</p>
          <h1 className="max-w-xl font-display text-4xl font-bold text-cloud sm:text-5xl">
            Find cheap trips, not just cheap flights.
          </h1>
          <p className="mt-4 max-w-xl leading-relaxed text-mist">
            Triplet watches fares from your selected airports and turns unusually cheap fares into trip
            ideas. Start free, upgrade when you want ongoing alerts. Prices are observed, not guaranteed.
          </p>
        </header>

        {status ? <Notice tone={status.tone}>{status.text}</Notice> : null}

        <div className="flex gap-7 border-b border-line" role="tablist" aria-label="Billing interval">
          {(["monthly", "yearly"] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={interval === option}
              onClick={() => setBillingInterval(option)}
              className={
                "-mb-px border-b-2 pb-2.5 font-mono text-[11px] font-semibold uppercase tracking-label transition-colors " +
                (interval === option ? "border-mint text-mint" : "border-transparent text-mist hover:text-cloud")
              }
            >
              {option === "monthly"
                ? "Monthly"
                : yearlySavings
                  ? `Yearly · save ${yearlySavings}%`
                  : "Yearly"}
            </button>
          ))}
        </div>

        {/* Two plans on one shared hairline grid. */}
        <div className="grid border-y border-line sm:grid-cols-2 sm:divide-x sm:divide-line">
          <div className="flex flex-col px-0 py-8 sm:px-8 sm:pl-0">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
              {free?.name ?? "Free"}
            </span>
            <span className="mono-num mt-3 font-display text-5xl font-bold leading-none text-coral">€0</span>
            <span className="mt-2 text-sm text-mist">For trying Triplet.</span>
            <ul className="mt-6 flex-1">
              {(free?.features ?? []).map((feature) => (
                <li key={feature} className="border-t border-line py-2.5 text-sm text-mist">
                  {feature}
                </li>
              ))}
            </ul>
            <ButtonLink href="/discover" variant="secondary" className="mt-8 w-full">
              Start searching
            </ButtonLink>
          </div>

          <div className="flex flex-col px-0 py-8 sm:px-8 sm:pr-0">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
              {pro?.name ?? "Triplet Pro"}
            </span>
            <span className="mono-num mt-3 font-display text-5xl font-bold leading-none text-coral">{proPrice}</span>
            <span className="mt-2 text-sm text-mist">For flexible travelers.</span>
            <ul className="mt-6 flex-1">
              {(pro?.features ?? []).map((feature) => (
                <li key={feature} className="border-t border-line py-2.5 text-sm text-mist">
                  {feature}
                </li>
              ))}
            </ul>
            {proCta}
          </div>
        </div>

        {/* Free trial */}
        <section className="border border-line bg-ink-raised p-6 sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-lg">
              <h2 className="font-display text-2xl font-bold text-cloud">
                Try Triplet Pro free for {trialDays} days
              </h2>
              <p className="mt-2 text-sm leading-relaxed text-mist">
                No card required. Get enough access to test real alerts, open-jaw suggestions, and your
                travel profile.
              </p>
              <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-1">
                {(trialPlan?.features ?? []).map((feature) => (
                  <li key={feature} className="font-mono text-[11px] uppercase tracking-[0.06em] text-mist/80">
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
            <div className="shrink-0 self-center">{trialCta()}</div>
          </div>
          <p className="mt-5 border-t border-line pt-4 font-mono text-[10px] uppercase tracking-label text-mist/60">
            No card required. Prices are never guaranteed and may change after you open the provider.
          </p>
        </section>

        <section>
          <h2 className="mb-4 font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
            Compare plans
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="font-mono text-[10px] uppercase tracking-label text-mist">
                  <th className="pb-2 pr-4 font-semibold">Feature</th>
                  <th className="pb-2 pr-4 font-semibold">Free</th>
                  <th className="pb-2 font-semibold text-mint">Pro</th>
                </tr>
              </thead>
              <tbody className="text-mist">
                {comparisonRows.map((row: { label: string; free: string; pro: string }) => (
                  <tr key={row.label} className="border-t border-line">
                    <td className="py-2.5 pr-4">{row.label}</td>
                    <td className="mono-num py-2.5 pr-4">{row.free}</td>
                    <td className="mono-num py-2.5 text-mint">{row.pro}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-5 font-mono text-[10px] uppercase tracking-label text-mist/70">
            Triplet finds and monitors fare opportunities. It does not sell flights, and prices are never
            guaranteed. Check the final price with the provider before booking.
          </p>
        </section>

        <section className="border-t border-line pt-8">
          <h2 className="mb-5 font-mono text-[11px] font-semibold uppercase tracking-label text-mist">FAQ</h2>
          <div className="space-y-5 text-sm">
            {FAQ.map((item) => (
              <div key={item.q}>
                <p className="font-semibold text-cloud">{item.q}</p>
                <p className="mt-1 leading-relaxed text-mist">{item.a}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
