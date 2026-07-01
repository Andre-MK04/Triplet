"use client";

import { FormEvent, useEffect, useState } from "react";

type AuthUser = {
  id: string;
  email: string;
  displayName?: string | null;
  isVerified: boolean;
  createdAt: string;
};

type SavedSearch = {
  id: string;
  email: string;
  name?: string | null;
  originAirports: string[];
  startDate: string;
  endDate: string;
  maxBudget: number;
  frequency: string;
  isActive: boolean;
  lastCheckedAt?: string | null;
  lastNotifiedAt?: string | null;
};

type AuthResponse = {
  user: AuthUser;
  message: string;
};

type BillingStatus = {
  plan: string;
  subscriptionStatus: string;
  currentPeriodEnd?: string | null;
  cancelAtPeriodEnd: boolean;
  limits: {
    savedSearchLimit: number;
    aiSearchesPerDay: number;
    maxOriginAirports: number;
    allowedAlertFrequencies: string[];
  };
  usage: {
    aiSearchesToday: number;
    aiSearchesPerDay: number;
    activeSavedSearches: number;
    savedSearchLimit: number;
  };
  canUpgrade: boolean;
  canManageBilling: boolean;
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export default function Dashboard() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [status, setStatus] = useState("");
  const [passwordForm, setPasswordForm] = useState({ currentPassword: "", newPassword: "" });

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard() {
    setStatus("");
    const authResponse = await fetch(`${apiBaseUrl}/auth/me`, { credentials: "include" });
    if (!authResponse.ok) {
      setStatus("Log in to view your dashboard.");
      return;
    }
    const authData: AuthResponse = await authResponse.json();
    setUser(authData.user);

    const searchesResponse = await fetch(`${apiBaseUrl}/me/saved-searches`, { credentials: "include" });
    if (!searchesResponse.ok) {
      setStatus("Could not load saved searches.");
      return;
    }
    setSavedSearches(await searchesResponse.json());

    const billingResponse = await fetch(`${apiBaseUrl}/billing/status`, { credentials: "include" });
    if (billingResponse.ok) {
      setBilling(await billingResponse.json());
    }
  }

  async function deactivate(id: string) {
    const response = await fetch(`${apiBaseUrl}/me/saved-searches/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!response.ok) {
      setStatus("Could not deactivate that alert.");
      return;
    }
    setSavedSearches((items) => items.map((item) => (item.id === id ? { ...item, isActive: false } : item)));
  }

  async function runNow(id: string) {
    setStatus("Checking alert...");
    const response = await fetch(`${apiBaseUrl}/me/saved-searches/${id}/run`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      setStatus("Could not run that alert.");
      return;
    }
    const data = await response.json();
    setStatus(`Checked alert. ${data.resultCount ?? 0} matching trip(s), best price ${data.bestPrice ? `€${Math.round(data.bestPrice)}` : "not found"}.`);
    loadDashboard();
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("");
    const response = await fetch(`${apiBaseUrl}/auth/change-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(passwordForm),
    });
    if (!response.ok) {
      setStatus("Could not change password.");
      return;
    }
    setPasswordForm({ currentPassword: "", newPassword: "" });
    setStatus("Password changed.");
  }

  async function startCheckout() {
    const response = await fetch(`${apiBaseUrl}/billing/create-checkout-session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ interval: "monthly" }),
    });
    if (!response.ok) {
      setStatus("Billing is not enabled in this environment.");
      return;
    }
    const data = await response.json();
    window.location.href = data.checkoutUrl;
  }

  async function manageBilling() {
    const response = await fetch(`${apiBaseUrl}/billing/create-portal-session`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      setStatus("Could not open billing portal.");
      return;
    }
    const data = await response.json();
    window.location.href = data.portalUrl;
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <section className="mx-auto flex max-w-6xl flex-col gap-8">
        <div className="flex items-center justify-between gap-4">
          <a className="text-sm font-semibold uppercase tracking-[0.22em] text-mint" href="/">
            TRIPLET
          </a>
          <a className="rounded-md border border-line px-3 py-2 text-sm text-white hover:border-mint" href="/">
            Search
          </a>
        </div>

        <div>
          <h1 className="text-3xl font-semibold text-white">Dashboard</h1>
          <p className="mt-2 text-slate-300">{user ? user.email : "Account dashboard"}</p>
        </div>

        {status ? <div className="rounded-lg border border-line bg-panel/80 p-4 text-sm text-slate-200">{status}</div> : null}

        {user ? (
          <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
            <section>
              {billing ? (
                <div className="mb-5 rounded-lg border border-line bg-panel/90 p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <h2 className="text-xl font-semibold text-white">Plan</h2>
                      <p className="mt-1 text-slate-300">
                        {billing.plan === "pro" ? "Triplet Pro" : "Free"} · {billing.subscriptionStatus}
                      </p>
                      {billing.currentPeriodEnd ? (
                        <p className="mt-1 text-sm text-slate-400">Renews through {billing.currentPeriodEnd.slice(0, 10)}</p>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-3">
                      {billing.canUpgrade ? (
                        <button type="button" onClick={startCheckout} className="rounded-md bg-mint px-3 py-2 text-sm font-semibold text-ink">
                          Upgrade
                        </button>
                      ) : null}
                      {billing.canManageBilling ? (
                        <button type="button" onClick={manageBilling} className="rounded-md border border-line px-3 py-2 text-sm text-white hover:border-mint">
                          Manage billing
                        </button>
                      ) : null}
                    </div>
                  </div>
                  <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                    <UsageLine label="AI searches today" used={billing.usage.aiSearchesToday} limit={billing.usage.aiSearchesPerDay} />
                    <UsageLine label="Saved alerts" used={billing.usage.activeSavedSearches} limit={billing.usage.savedSearchLimit} />
                  </div>
                </div>
              ) : null}
              <h2 className="mb-4 text-xl font-semibold text-white">Saved searches</h2>
              <div className="grid gap-4">
                {savedSearches.map((search) => (
                  <article key={search.id} className="rounded-lg border border-line bg-panel/90 p-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <h3 className="text-lg font-semibold text-white">{search.name || "Saved search"}</h3>
                        <p className="mt-1 text-sm text-slate-400">
                          {search.originAirports.join(", ")} · {search.startDate} to {search.endDate} · under €{Math.round(search.maxBudget)}
                        </p>
                      </div>
                      <span className={`rounded-md px-2.5 py-1 text-xs font-medium ${search.isActive ? "bg-mint/10 text-mint" : "bg-coral/10 text-coral"}`}>
                        {search.isActive ? "active" : "inactive"}
                      </span>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <button type="button" onClick={() => runNow(search.id)} className="rounded-md bg-mint px-3 py-2 text-sm font-semibold text-ink">
                        Run now
                      </button>
                      {search.isActive ? (
                        <button type="button" onClick={() => deactivate(search.id)} className="rounded-md border border-line px-3 py-2 text-sm text-white hover:border-coral">
                          Deactivate
                        </button>
                      ) : null}
                    </div>
                  </article>
                ))}
                {!savedSearches.length ? (
                  <div className="rounded-lg border border-line bg-panel/80 p-8 text-center text-slate-300">
                    No saved searches yet.
                  </div>
                ) : null}
              </div>
            </section>

            <form onSubmit={changePassword} className="h-fit rounded-lg border border-line bg-panel/90 p-5">
              <h2 className="text-xl font-semibold text-white">Password</h2>
              <label className="mt-4 block">
                <span className="mb-1.5 block text-sm font-medium text-slate-300">Current password</span>
                <input
                  type="password"
                  required
                  autoComplete="current-password"
                  value={passwordForm.currentPassword}
                  onChange={(event) => setPasswordForm({ ...passwordForm, currentPassword: event.target.value })}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </label>
              <label className="mt-4 block">
                <span className="mb-1.5 block text-sm font-medium text-slate-300">New password</span>
                <input
                  type="password"
                  required
                  minLength={12}
                  autoComplete="new-password"
                  value={passwordForm.newPassword}
                  onChange={(event) => setPasswordForm({ ...passwordForm, newPassword: event.target.value })}
                  className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
                />
              </label>
              <button type="submit" className="mt-5 w-full rounded-md bg-mint px-4 py-3 font-semibold text-ink">
                Change password
              </button>
            </form>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function UsageLine({ label, used, limit }: { label: string; used: number; limit: number }) {
  return (
    <div className="rounded-md border border-line bg-ink/55 p-3">
      <p className="text-slate-400">{label}</p>
      <p className="mt-1 font-semibold text-white">
        {used} / {limit}
      </p>
    </div>
  );
}
