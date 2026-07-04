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
  minTripLengthDays: number;
  maxTripLengthDays: number;
  maxBudget: number;
  maxGroundTransferHours: number;
  tripStyle: "one city" | "two nearby cities" | "surprise me";
  frequency: string;
  isActive: boolean;
  lastCheckedAt?: string | null;
  lastNotifiedAt?: string | null;
  lastBestPrice?: number | null;
};

type BillingStatus = {
  plan: string;
  subscriptionStatus: string;
  currentPeriodEnd?: string | null;
  cancelAtPeriodEnd: boolean;
  usage: {
    aiSearchesToday: number;
    aiSearchesPerDay: number;
    activeSavedSearches: number;
    savedSearchLimit: number;
  };
  canUpgrade: boolean;
  canManageBilling: boolean;
};

type DashboardResponse = {
  user: AuthUser;
  billing: BillingStatus;
  savedSearches: SavedSearch[];
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export default function Dashboard() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [editing, setEditing] = useState<SavedSearch | null>(null);
  const [status, setStatus] = useState("");
  const [passwordForm, setPasswordForm] = useState({ currentPassword: "", newPassword: "" });

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard() {
    setStatus("");
    const response = await fetch(`${apiBaseUrl}/me/dashboard`, { credentials: "include" });
    if (!response.ok) {
      setStatus("Log in to view your dashboard.");
      return;
    }
    const data: DashboardResponse = await response.json();
    setUser(data.user);
    setBilling(data.billing);
    setSavedSearches(data.savedSearches);
  }

  async function runNow(id: string) {
    setStatus("Checking alert...");
    const response = await fetch(`${apiBaseUrl}/me/saved-searches/${id}/run`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      setStatus("Could not preview that alert.");
      return;
    }
    const data = await response.json();
    setStatus(`Preview complete. ${data.resultCount ?? 0} matching trip(s), best price ${data.bestPrice ? `€${Math.round(data.bestPrice)}` : "not found"}.`);
    loadDashboard();
  }

  async function pause(id: string) {
    await updateAlertState(id, "pause");
  }

  async function resume(id: string) {
    await updateAlertState(id, "resume");
  }

  async function updateAlertState(id: string, action: "pause" | "resume") {
    const response = await fetch(`${apiBaseUrl}/me/saved-searches/${id}/${action}`, {
      method: "POST",
      credentials: "include",
    });
    if (!response.ok) {
      setStatus(`Could not ${action} that alert.`);
      return;
    }
    const updated = await response.json();
    setSavedSearches((items) => items.map((item) => (item.id === id ? updated : item)));
    loadDashboard();
  }

  async function deleteAlert(id: string) {
    const response = await fetch(`${apiBaseUrl}/me/saved-searches/${id}`, {
      method: "DELETE",
      credentials: "include",
    });
    if (!response.ok) {
      setStatus("Could not delete that alert.");
      return;
    }
    setSavedSearches((items) => items.filter((item) => item.id !== id));
    loadDashboard();
  }

  async function saveEdit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) {
      return;
    }
    const response = await fetch(`${apiBaseUrl}/me/saved-searches/${editing.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(editing),
    });
    if (!response.ok) {
      const message = await response.text();
      setStatus(message.includes("Weekly") ? "Weekly alerts are available on Triplet Pro." : "Could not save alert changes.");
      return;
    }
    const updated = await response.json();
    setSavedSearches((items) => items.map((item) => (item.id === updated.id ? updated : item)));
    setEditing(null);
    loadDashboard();
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

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
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

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <section className="mx-auto flex max-w-6xl flex-col gap-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <a className="text-sm font-semibold uppercase tracking-[0.22em] text-mint" href="/">
            TRIPLET
          </a>
          <nav className="flex items-center gap-4 text-sm text-slate-300">
            <a className="hover:text-white" href="/">Search</a>
            <a className="hover:text-white" href="/pricing">Pricing</a>
            <a className="hover:text-white" href="/account">Account</a>
          </nav>
        </div>

        <div>
          <h1 className="text-3xl font-semibold text-white">Welcome back</h1>
          <p className="mt-2 text-slate-300">{user ? user.displayName || user.email : "Log in to manage saved alerts."}</p>
        </div>

        {status ? <div className="rounded-lg border border-line bg-panel/80 p-4 text-sm text-slate-200">{status}</div> : null}

        {billing ? (
          <div className="grid gap-4 md:grid-cols-3">
            <SummaryCard label="Plan" value={billing.plan === "pro" ? "Triplet Pro" : "Free"} detail={billing.subscriptionStatus} />
            <SummaryCard label="Saved alerts" value={`${billing.usage.activeSavedSearches} / ${billing.usage.savedSearchLimit}`} />
            <SummaryCard label="AI searches today" value={`${billing.usage.aiSearchesToday} / ${billing.usage.aiSearchesPerDay}`} />
          </div>
        ) : null}

        {user ? (
          <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
            <section>
              <h2 className="mb-4 text-xl font-semibold text-white">Saved alerts</h2>
              <div className="grid gap-4">
                {savedSearches.map((search) => (
                  <AlertCard
                    key={search.id}
                    search={search}
                    onPreview={() => runNow(search.id)}
                    onEdit={() => setEditing(search)}
                    onPause={() => pause(search.id)}
                    onResume={() => resume(search.id)}
                    onDelete={() => deleteAlert(search.id)}
                  />
                ))}
                {!savedSearches.length ? (
                  <div className="rounded-lg border border-line bg-panel/80 p-8 text-center text-slate-300">
                    <h3 className="text-xl font-semibold text-white">No saved alerts yet.</h3>
                    <p className="mt-2">Create your first alert after running a trip search.</p>
                    <a className="mt-4 inline-block rounded-md bg-mint px-4 py-3 font-semibold text-ink" href="/">
                      Create your first alert
                    </a>
                  </div>
                ) : null}
              </div>
            </section>

            <aside className="space-y-6">
              <div className="rounded-lg border border-line bg-panel/90 p-5">
                <h2 className="text-xl font-semibold text-white">Billing</h2>
                <p className="mt-2 text-sm text-slate-300">
                  {billing?.plan === "pro"
                    ? "Manage your subscription and invoices in Stripe."
                    : "Upgrade for more alerts, more AI searches, and weekly alert options."}
                </p>
                {billing?.canManageBilling ? (
                  <button type="button" onClick={manageBilling} className="mt-4 w-full rounded-md border border-line px-4 py-3 font-semibold text-white hover:border-mint">
                    Manage billing
                  </button>
                ) : (
                  <button type="button" onClick={startCheckout} className="mt-4 w-full rounded-md bg-mint px-4 py-3 font-semibold text-ink">
                    Upgrade to Pro
                  </button>
                )}
              </div>

              <form onSubmit={changePassword} className="rounded-lg border border-line bg-panel/90 p-5">
                <h2 className="text-xl font-semibold text-white">Password</h2>
                <TextField label="Current password" type="password" value={passwordForm.currentPassword} onChange={(value) => setPasswordForm({ ...passwordForm, currentPassword: value })} />
                <TextField label="New password" type="password" value={passwordForm.newPassword} onChange={(value) => setPasswordForm({ ...passwordForm, newPassword: value })} />
                <button type="submit" className="mt-5 w-full rounded-md bg-mint px-4 py-3 font-semibold text-ink">
                  Change password
                </button>
              </form>
            </aside>
          </div>
        ) : null}
      </section>

      {editing ? (
        <EditAlertModal alert={editing} onChange={setEditing} onClose={() => setEditing(null)} onSubmit={saveEdit} />
      ) : null}
    </main>
  );
}

function SummaryCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-lg border border-line bg-panel/90 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-white">{value}</p>
      {detail ? <p className="mt-1 text-sm text-mint">{detail}</p> : null}
    </div>
  );
}

function AlertCard({
  search,
  onPreview,
  onEdit,
  onPause,
  onResume,
  onDelete,
}: {
  search: SavedSearch;
  onPreview: () => void;
  onEdit: () => void;
  onPause: () => void;
  onResume: () => void;
  onDelete: () => void;
}) {
  return (
    <article className="rounded-lg border border-line bg-panel/90 p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">{search.name || "Saved alert"}</h3>
          <p className="mt-1 text-sm text-slate-400">
            {search.originAirports.join(", ")} · {search.startDate} to {search.endDate} · {search.minTripLengthDays}-{search.maxTripLengthDays} days · under €{Math.round(search.maxBudget)}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {search.frequency} · last checked {search.lastCheckedAt ? search.lastCheckedAt.slice(0, 10) : "never"} ·
            last notified {search.lastNotifiedAt ? search.lastNotifiedAt.slice(0, 10) : "never"} ·
            best price {search.lastBestPrice ? `€${Math.round(search.lastBestPrice)}` : "not yet"}
          </p>
        </div>
        <span className={`rounded-md px-2.5 py-1 text-xs font-medium ${search.isActive ? "bg-mint/10 text-mint" : "bg-coral/10 text-coral"}`}>
          {search.isActive ? "active" : "paused"}
        </span>
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={onPreview} className="rounded-md bg-mint px-3 py-2 text-sm font-semibold text-ink">Preview results</button>
        <button type="button" onClick={onEdit} className="rounded-md border border-line px-3 py-2 text-sm text-white hover:border-mint">Edit</button>
        {search.isActive ? (
          <button type="button" onClick={onPause} className="rounded-md border border-line px-3 py-2 text-sm text-white hover:border-coral">Pause</button>
        ) : (
          <button type="button" onClick={onResume} className="rounded-md border border-line px-3 py-2 text-sm text-white hover:border-mint">Resume</button>
        )}
        <button type="button" onClick={onDelete} className="rounded-md border border-coral/50 px-3 py-2 text-sm text-coral">Delete</button>
      </div>
    </article>
  );
}

function EditAlertModal({
  alert,
  onChange,
  onClose,
  onSubmit,
}: {
  alert: SavedSearch;
  onChange: (alert: SavedSearch) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink/75 px-4">
      <form onSubmit={onSubmit} className="w-full max-w-2xl rounded-lg border border-line bg-panel p-5">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-white">Edit alert</h2>
          <button type="button" onClick={onClose} className="rounded-md border border-line px-3 py-1.5 text-sm text-white">Close</button>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField label="Name" value={alert.name || ""} onChange={(value) => onChange({ ...alert, name: value })} />
          <TextField label="Origin airports" value={alert.originAirports.join(", ")} onChange={(value) => onChange({ ...alert, originAirports: value.split(",").map((code) => code.trim().toUpperCase()).filter(Boolean) })} />
          <TextField label="Start date" type="date" value={alert.startDate} onChange={(value) => onChange({ ...alert, startDate: value })} />
          <TextField label="End date" type="date" value={alert.endDate} onChange={(value) => onChange({ ...alert, endDate: value })} />
          <TextField label="Max budget" type="number" value={String(alert.maxBudget)} onChange={(value) => onChange({ ...alert, maxBudget: Number(value) })} />
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-slate-300">Frequency</span>
            <select value={alert.frequency} onChange={(event) => onChange({ ...alert, frequency: event.target.value })} className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2">
              <option value="daily">daily</option>
              <option value="weekly">weekly</option>
            </select>
          </label>
        </div>
        <button type="submit" className="mt-5 rounded-md bg-mint px-4 py-3 font-semibold text-ink">Save changes</button>
      </form>
    </div>
  );
}

function TextField({ label, value, onChange, type = "text" }: { label: string; value: string; onChange: (value: string) => void; type?: string }) {
  return (
    <label className="mt-4 block">
      <span className="mb-1.5 block text-sm font-medium text-slate-300">{label}</span>
      <input type={type} value={value} onChange={(event) => onChange(event.target.value)} className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2" />
    </label>
  );
}
