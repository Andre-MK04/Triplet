"use client";

import { useEffect, useState } from "react";

type AuthUser = {
  email: string;
};

type AuthResponse = {
  user: AuthUser;
};

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

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export default function PricingPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [interval, setInterval] = useState<"monthly" | "yearly">("monthly");
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch(`${apiBaseUrl}/auth/me`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : null))
      .then((data: AuthResponse | null) => setUser(data?.user ?? null))
      .catch(() => undefined);
    fetch(`${apiBaseUrl}/billing/plans`)
      .then((response) => response.json())
      .then(setPlans)
      .catch(() => setStatus("Could not load plans."));
  }, []);

  async function upgrade() {
    if (!user) {
      setStatus("Log in or create an account before upgrading.");
      return;
    }
    setStatus("");
    const response = await fetch(`${apiBaseUrl}/billing/create-checkout-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ interval }),
    });
    if (!response.ok) {
      const message = await response.text();
      setStatus(message.includes("Billing is not enabled") ? "Billing is not enabled in this environment." : "Could not start checkout.");
      return;
    }
    const data = await response.json();
    window.location.href = data.checkoutUrl;
  }

  const free = plans.find((plan) => plan.plan === "free");
  const pro = plans.find((plan) => plan.plan === "pro");

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <section className="mx-auto flex max-w-5xl flex-col gap-8">
        <div className="flex items-center justify-between gap-4">
          <a className="text-sm font-semibold uppercase tracking-[0.22em] text-mint" href="/">
            TRIPLET
          </a>
          <a className="rounded-md border border-line px-3 py-2 text-sm text-white hover:border-mint" href="/dashboard">
            Dashboard
          </a>
        </div>
        <div>
          <h1 className="text-3xl font-semibold text-white">Plans</h1>
          <p className="mt-2 text-slate-300">Start free and upgrade when you need more alerts and AI searches.</p>
          <p className="mt-2 text-sm text-slate-500">Triplet helps discover fare opportunities. Prices can change and fares are not guaranteed.</p>
        </div>
        <div className="flex w-fit rounded-md border border-line bg-panel p-1">
          {(["monthly", "yearly"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setInterval(option)}
              className={`rounded px-4 py-2 text-sm font-semibold ${interval === option ? "bg-mint text-ink" : "text-slate-300"}`}
            >
              {option}
            </button>
          ))}
        </div>
        {status ? <div className="rounded-lg border border-line bg-panel/80 p-4 text-sm text-slate-200">{status}</div> : null}
        <div className="grid gap-5 md:grid-cols-2">
          {free ? (
            <PlanCard plan={free} actionLabel="Start free" actionHref="/" />
          ) : null}
          {pro ? (
            <PlanCard plan={pro} actionLabel="Upgrade to Pro" onAction={upgrade} highlight />
          ) : null}
        </div>
        <section className="rounded-lg border border-line bg-panel/80 p-5">
          <h2 className="text-xl font-semibold text-white">Feature comparison</h2>
          <div className="mt-4 grid gap-3 text-sm text-slate-300 sm:grid-cols-2">
            <div>Free: basic trip search, 3 saved alerts, 5 AI searches/day, daily alerts.</div>
            <div>Pro: 30 saved alerts, 100 AI searches/day, more origin airports, daily or weekly alerts.</div>
          </div>
        </section>
        <section className="rounded-lg border border-line bg-panel/80 p-5">
          <h2 className="text-xl font-semibold text-white">FAQ</h2>
          <div className="mt-4 space-y-4 text-sm text-slate-300">
            <p><span className="font-semibold text-white">Does Triplet book flights?</span> No. Triplet helps find and monitor trip ideas; booking stays outside the app.</p>
            <p><span className="font-semibold text-white">Are prices guaranteed?</span> No. Fares can change quickly, especially in demo or cached data modes.</p>
            <p><span className="font-semibold text-white">Can I cancel Pro?</span> Yes, paid web subscriptions are managed through Stripe billing portal.</p>
          </div>
        </section>
      </section>
    </main>
  );
}

function PlanCard({
  plan,
  actionLabel,
  actionHref,
  onAction,
  highlight = false,
}: {
  plan: BillingPlan;
  actionLabel: string;
  actionHref?: string;
  onAction?: () => void;
  highlight?: boolean;
}) {
  return (
    <article className={`rounded-lg border p-5 ${highlight ? "border-mint bg-mint/10" : "border-line bg-panel/90"}`}>
      <h2 className="text-xl font-semibold text-white">{plan.name}</h2>
      <p className="mt-2 text-2xl font-semibold text-mint">{plan.priceLabel}</p>
      <ul className="mt-5 space-y-2 text-sm text-slate-300">
        {plan.features.map((feature) => (
          <li key={feature}>{feature}</li>
        ))}
      </ul>
      {actionHref ? (
        <a className="mt-5 block rounded-md bg-mint px-4 py-3 text-center font-semibold text-ink" href={actionHref}>
          {actionLabel}
        </a>
      ) : (
        <button type="button" onClick={onAction} className="mt-5 w-full rounded-md bg-mint px-4 py-3 font-semibold text-ink">
          {actionLabel}
        </button>
      )}
    </article>
  );
}
