"use client";

import { FormEvent, useEffect, useState } from "react";

type AuthUser = {
  id: string;
  email: string;
  displayName?: string | null;
  isVerified: boolean;
  createdAt: string;
};

type BillingStatus = {
  plan: string;
  subscriptionStatus: string;
  canManageBilling: boolean;
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export default function AccountPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [passwordForm, setPasswordForm] = useState({ currentPassword: "", newPassword: "" });
  const [status, setStatus] = useState("");

  useEffect(() => {
    loadAccount();
  }, []);

  async function loadAccount() {
    const me = await fetch(`${apiBaseUrl}/auth/me`, { credentials: "include" });
    if (!me.ok) {
      setStatus("Log in to manage your account.");
      return;
    }
    const data = await me.json();
    setUser(data.user);
    setDisplayName(data.user.displayName || "");
    const billingResponse = await fetch(`${apiBaseUrl}/billing/status`, { credentials: "include" });
    if (billingResponse.ok) {
      setBilling(await billingResponse.json());
    }
  }

  async function updateProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch(`${apiBaseUrl}/auth/me`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ displayName: displayName || null }),
    });
    setStatus(response.ok ? "Profile updated." : "Could not update profile.");
    loadAccount();
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch(`${apiBaseUrl}/auth/change-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(passwordForm),
    });
    setStatus(response.ok ? "Password changed." : "Could not change password.");
    if (response.ok) {
      setPasswordForm({ currentPassword: "", newPassword: "" });
    }
  }

  async function logout() {
    await fetch(`${apiBaseUrl}/auth/logout`, { method: "POST", credentials: "include" });
    window.location.href = "/";
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
      <section className="mx-auto max-w-3xl">
        <div className="flex items-center justify-between">
          <a className="text-sm font-semibold uppercase tracking-[0.22em] text-mint" href="/">TRIPLET</a>
          <a className="rounded-md border border-line px-3 py-2 text-sm text-white hover:border-mint" href="/dashboard">Dashboard</a>
        </div>
        <h1 className="mt-8 text-3xl font-semibold text-white">Account</h1>
        {status ? <div className="mt-4 rounded-lg border border-line bg-panel/80 p-4 text-sm text-slate-200">{status}</div> : null}
        {user ? (
          <div className="mt-6 grid gap-5">
            <div className="rounded-lg border border-line bg-panel/90 p-5">
              <p className="text-sm text-slate-400">Email</p>
              <p className="mt-1 font-semibold text-white">{user.email}</p>
              <p className="mt-3 text-sm text-slate-400">Plan</p>
              <p className="mt-1 font-semibold text-mint">{billing?.plan === "pro" ? "Triplet Pro" : "Free"} · {billing?.subscriptionStatus ?? "none"}</p>
            </div>
            <form onSubmit={updateProfile} className="rounded-lg border border-line bg-panel/90 p-5">
              <h2 className="text-xl font-semibold text-white">Profile</h2>
              <label className="mt-4 block">
                <span className="mb-1.5 block text-sm font-medium text-slate-300">Display name</span>
                <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2" />
              </label>
              <button className="mt-4 rounded-md bg-mint px-4 py-3 font-semibold text-ink">Save profile</button>
            </form>
            <form onSubmit={changePassword} className="rounded-lg border border-line bg-panel/90 p-5">
              <h2 className="text-xl font-semibold text-white">Password</h2>
              <label className="mt-4 block">
                <span className="mb-1.5 block text-sm font-medium text-slate-300">Current password</span>
                <input type="password" value={passwordForm.currentPassword} onChange={(event) => setPasswordForm({ ...passwordForm, currentPassword: event.target.value })} className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2" />
              </label>
              <label className="mt-4 block">
                <span className="mb-1.5 block text-sm font-medium text-slate-300">New password</span>
                <input type="password" minLength={12} value={passwordForm.newPassword} onChange={(event) => setPasswordForm({ ...passwordForm, newPassword: event.target.value })} className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2" />
              </label>
              <button className="mt-4 rounded-md bg-mint px-4 py-3 font-semibold text-ink">Change password</button>
            </form>
            <div className="flex flex-wrap gap-3">
              {billing?.canManageBilling ? (
                <button type="button" onClick={manageBilling} className="rounded-md border border-line px-4 py-3 font-semibold text-white hover:border-mint">Manage billing</button>
              ) : (
                <a className="rounded-md border border-line px-4 py-3 font-semibold text-white hover:border-mint" href="/pricing">View pricing</a>
              )}
              <button type="button" onClick={logout} className="rounded-md bg-mint px-4 py-3 font-semibold text-ink">Log out</button>
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}
