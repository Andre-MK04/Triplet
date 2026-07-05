"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Badge } from "../../components/ui/Badge";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
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

export default function PricingPage() {
  const { user } = useAuth();
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [interval, setBillingInterval] = useState<"monthly" | "yearly">("monthly");
  const [status, setStatus] = useState("");

  useEffect(() => {
    apiGet<BillingPlan[]>("/billing/plans")
      .then(setPlans)
      .catch(() => setStatus("Could not load plans. Is the API running?"));
  }, []);

  async function upgrade() {
    if (!user) {
      window.location.href = "/signup";
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

  const free = plans.find((plan) => plan.plan === "free");
  const pro = plans.find((plan) => plan.plan === "pro");

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-8 pb-10">
        <header className="text-center">
          <h1 className="font-display text-4xl font-bold text-cloud">Free to watch, Pro to hunt harder</h1>
          <p className="mx-auto mt-3 max-w-xl text-mist">
            Start free and upgrade when you need more watches and AI searches. Triplet finds fare
            opportunities — prices can change and are never guaranteed.
          </p>
        </header>

        <div className="mx-auto flex w-fit rounded-full bg-ink-soft/80 p-1" role="tablist" aria-label="Billing interval">
          {(["monthly", "yearly"] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={interval === option}
              onClick={() => setBillingInterval(option)}
              className={
                "rounded-full px-5 py-2 text-sm font-semibold transition " +
                (interval === option ? "bg-mint text-ink" : "text-mist hover:text-cloud")
              }
            >
              {option === "monthly" ? "Monthly" : "Yearly"}
            </button>
          ))}
        </div>

        {status ? <Notice tone="info">{status}</Notice> : null}

        <div className="grid gap-5 md:grid-cols-2">
          {free ? (
            <Card hover className="flex flex-col">
              <h2 className="font-display text-xl font-bold text-cloud">{free.name}</h2>
              <p className="mt-2 font-display text-3xl font-bold text-mint">{free.priceLabel}</p>
              <ul className="mt-5 flex-1 space-y-2 text-sm text-mist">
                {free.features.map((feature) => (
                  <li key={feature} className="flex gap-2"><span className="text-mint" aria-hidden>✓</span>{feature}</li>
                ))}
              </ul>
              <ButtonLink href={user ? "/discover" : "/signup"} variant="secondary" className="mt-6 w-full">
                {user ? "Keep exploring" : "Start free"}
              </ButtonLink>
            </Card>
          ) : null}
          {pro ? (
            <Card hover className="relative flex flex-col border-mint/40">
              <Badge tone="mint" className="absolute -top-3 left-5">Most deal-hungry</Badge>
              <h2 className="font-display text-xl font-bold text-cloud">{pro.name}</h2>
              <p className="mt-2 font-display text-3xl font-bold text-mint">{pro.priceLabel}</p>
              <ul className="mt-5 flex-1 space-y-2 text-sm text-mist">
                {pro.features.map((feature) => (
                  <li key={feature} className="flex gap-2"><span className="text-mint" aria-hidden>✓</span>{feature}</li>
                ))}
              </ul>
              <Button className="mt-6 w-full" onClick={() => void upgrade()}>Upgrade to Pro</Button>
            </Card>
          ) : null}
        </div>

        <Card>
          <h2 className="font-display text-lg font-bold text-cloud">Compare limits</h2>
          <div className="mt-4 overflow-x-auto">
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
        </Card>

        <Card>
          <h2 className="font-display text-lg font-bold text-cloud">FAQ</h2>
          <div className="mt-4 space-y-4 text-sm">
            {FAQ.map((item) => (
              <div key={item.q}>
                <p className="font-semibold text-cloud">{item.q}</p>
                <p className="mt-1 text-mist">{item.a}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
