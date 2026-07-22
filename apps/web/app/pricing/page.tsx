"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Notice } from "../../components/ui/Misc";
import { apiGet, apiPost } from "../../lib/api";

type BillingPlan = {
  plan: string;
  name: string;
  priceLabel: string;
  features: string[];
  limits: {
    savedSearchLimit: number;
    aiSearchesPerDay: number;
    maxOriginAirports: number;
    allowedAlertFrequencies: string[];
  };
};

const FAQ = [
  {
    q: "Does Triplet book flights?",
    a: "No. Triplet finds and monitors trip ideas; booking always happens with the airline or provider.",
  },
  {
    q: "Are prices guaranteed?",
    a: "No. Fares are observed at check time and can change quickly — especially in demo or cached data modes.",
  },
  {
    q: "Can I cancel Pro?",
    a: "Yes. Paid web subscriptions are managed through the Stripe billing portal — cancel anytime.",
  },
];

type BillingStatus = {
  plan: string;
  canManageBilling: boolean;
};

export default function PricingPage() {
  const { user } = useAuth();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [interval, setBillingInterval] = useState<"monthly" | "yearly">("monthly");
  const [status, setStatus] = useState("");

  useEffect(() => {
    apiGet<BillingPlan[]>("/billing/plans")
      .then(setPlans)
      .catch(() => setStatus("Could not load plans. Is the API running?"));
  }, []);

  useEffect(() => {
    if (!user) {
      setBilling(null);
      return;
    }
    apiGet<BillingStatus>("/billing/status").then(setBilling).catch(() => setBilling(null));
  }, [user]);

  async function upgrade() {
    if (!user) {
      window.location.href = "/login";
      return;
    }
    setStatus("");
    try {
      const data = await apiPost<{ checkoutUrl: string }>("/billing/create-checkout-session", { interval });
      window.location.href = data.checkoutUrl;
    } catch {
      setStatus("Billing is not enabled in this environment yet.");
    }
  }

  async function manageBilling() {
    setStatus("");
    try {
      const data = await apiPost<{ portalUrl: string }>("/billing/create-portal-session");
      window.location.href = data.portalUrl;
    } catch {
      setStatus("Could not open the billing portal.");
    }
  }

  const free = plans.find((plan) => plan.plan === "free");
  const pro = plans.find((plan) => plan.plan === "pro");

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-14 pb-16">
        <header>
          <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">Pricing</p>
          <h1 className="max-w-xl font-display text-4xl font-bold text-cloud sm:text-5xl">
            Free to watch, Pro to hunt harder.
          </h1>
          <p className="mt-4 max-w-xl leading-relaxed text-mist">
            Start free and upgrade when you need more watches and AI searches. Triplet finds fare
            opportunities — prices can change and are never guaranteed.
          </p>
        </header>

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
              {option === "monthly" ? "Monthly" : "Yearly"}
            </button>
          ))}
        </div>

        {status ? <Notice tone="info">{status}</Notice> : null}

        {/* Two plans on one shared hairline grid — a typographic comparison, not floating cards. */}
        <div className="grid border-y border-line sm:grid-cols-2 sm:divide-x sm:divide-line">
          {[
            { plan: free, cta: (
              <ButtonLink href="/discover" variant="secondary" className="mt-8 w-full">
                Start searching
              </ButtonLink>
            ) },
            { plan: pro, cta: !user ? (
              <ButtonLink href="/login" className="mt-8 w-full">
                Log in to upgrade
              </ButtonLink>
            ) : billing?.plan === "pro" ? (
              <Button variant="secondary" className="mt-8 w-full" onClick={() => void manageBilling()}>
                Manage billing
              </Button>
            ) : (
              <Button className="mt-8 w-full" onClick={() => void upgrade()}>Upgrade to Pro</Button>
            ) },
          ].map(({ plan, cta }) =>
            plan ? (
              <div key={plan.plan} className="flex flex-col px-0 py-8 sm:px-8 first:sm:pl-0 last:sm:pr-0">
                <span className="font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
                  {plan.name}
                </span>
                <span className="mono-num mt-3 font-display text-5xl font-bold leading-none text-coral">
                  {plan.priceLabel}
                </span>
                <ul className="mt-8 flex-1">
                  {plan.features.map((feature) => (
                    <li key={feature} className="border-t border-line py-2.5 text-sm text-mist">
                      {feature}
                    </li>
                  ))}
                </ul>
                {cta}
              </div>
            ) : null,
          )}
        </div>

        <p className="font-mono text-[10px] uppercase tracking-label text-mist/70">
          Triplet finds and monitors fare opportunities. It does not sell flights, and prices are
          never guaranteed.
        </p>

        <section>
          <h2 className="mb-4 font-mono text-[11px] font-semibold uppercase tracking-label text-mist">
            Compare limits
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-xs uppercase tracking-wide text-mist">
                  <th className="pb-2 pr-4 font-semibold">Limit</th>
                  <th className="pb-2 pr-4 font-semibold">Free</th>
                  <th className="pb-2 font-semibold">Pro</th>
                </tr>
              </thead>
              <tbody className="text-mist">
                <tr className="border-t border-line">
                  <td className="py-2.5 pr-4">Saved watches</td>
                  <td className="py-2.5 pr-4">{free?.limits.savedSearchLimit ?? 3}</td>
                  <td className="py-2.5 text-mint">{pro?.limits.savedSearchLimit ?? 30}</td>
                </tr>
                <tr className="border-t border-line">
                  <td className="py-2.5 pr-4">AI searches per day</td>
                  <td className="py-2.5 pr-4">{free?.limits.aiSearchesPerDay ?? 5}</td>
                  <td className="py-2.5 text-mint">{pro?.limits.aiSearchesPerDay ?? 100}</td>
                </tr>
                <tr className="border-t border-line">
                  <td className="py-2.5 pr-4">Origin airports</td>
                  <td className="py-2.5 pr-4">{free?.limits.maxOriginAirports ?? 6}</td>
                  <td className="py-2.5 text-mint">{pro?.limits.maxOriginAirports ?? 12}</td>
                </tr>
                <tr className="border-t border-line">
                  <td className="py-2.5 pr-4">Alert frequencies</td>
                  <td className="py-2.5 pr-4">{free?.limits.allowedAlertFrequencies.join(", ") ?? "daily"}</td>
                  <td className="py-2.5 text-mint">{pro?.limits.allowedAlertFrequencies.join(", ") ?? "daily, weekly"}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-5 font-mono text-[10px] uppercase tracking-label text-mist/70">
            Both plans see the same fares. We never mark prices up.
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
