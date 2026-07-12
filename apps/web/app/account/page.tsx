"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Input";
import { EmptyState, Notice, Spinner } from "../../components/ui/Misc";
import { apiDelete, apiGet, apiPatch, apiPost } from "../../lib/api";

type AccountBilling = {
  plan: string;
  subscriptionStatus: string;
  canManageBilling: boolean;
};

export default function AccountPage() {
  const { user, isLoading, refresh, logout } = useAuth();
  const [billing, setBilling] = useState<AccountBilling | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [passwordForm, setPasswordForm] = useState({ currentPassword: "", newPassword: "" });
  const [status, setStatus] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    if (!user) return;
    setDisplayName(user.displayName ?? "");
    apiGet<AccountBilling>("/billing/status").then(setBilling).catch(() => undefined);
  }, [user]);

  async function updateProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await apiPatch("/auth/me", { displayName: displayName || null });
      setStatus({ tone: "success", text: "Profile updated." });
      await refresh();
    } catch {
      setStatus({ tone: "error", text: "Could not update profile." });
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await apiPost("/auth/change-password", passwordForm);
      setPasswordForm({ currentPassword: "", newPassword: "" });
      setStatus({ tone: "success", text: "Password changed." });
    } catch {
      setStatus({ tone: "error", text: "Could not change password. Check your current password." });
    }
  }

  async function manageBilling() {
    try {
      const data = await apiPost<{ portalUrl: string }>("/billing/create-portal-session");
      window.location.href = data.portalUrl;
    } catch {
      setStatus({ tone: "error", text: "Could not open the billing portal." });
    }
  }

  async function downloadData() {
    try {
      const data = await apiGet<Record<string, unknown>>("/me/export");
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "triplet-my-data.json";
      link.click();
      URL.revokeObjectURL(url);
      setStatus({ tone: "success", text: "Your data has been downloaded." });
    } catch {
      setStatus({ tone: "error", text: "Could not export your data." });
    }
  }

  async function deleteAccount() {
    if (!window.confirm("Permanently delete your account and all your data? This cannot be undone.")) {
      return;
    }
    try {
      await apiDelete("/auth/me");
      window.location.href = "/?deleted=1";
    } catch {
      setStatus({ tone: "error", text: "Could not delete your account. Please try again." });
    }
  }

  if (isLoading) {
    return (
      <AppShell>
        <div className="flex justify-center py-24"><Spinner /></div>
      </AppShell>
    );
  }

  if (!user) {
    return (
      <AppShell>
        <EmptyState icon="🔐" title="Log in to manage your account" action={<ButtonLink href="/login">Log in</ButtonLink>} />
      </AppShell>
    );
  }

  const sectionLabel = "mb-5 block font-mono text-[11px] font-semibold uppercase tracking-label text-mist";

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl pb-16">
        <header className="pb-8">
          <h1 className="font-display text-4xl font-bold text-cloud">Account</h1>
          <p className="mono-num mt-3 font-mono text-xs text-mist">
            {user.email} ·{" "}
            <span className={billing?.plan === "pro" ? "text-mint" : "text-mist"}>
              {billing?.plan === "pro" ? "TRIPLET PRO" : "FREE PLAN"}
            </span>
          </p>
        </header>

        {status ? (
          <div className="mb-6">
            <Notice tone={status.tone}>{status.text}</Notice>
          </div>
        ) : null}

        <section className="border-t border-line py-8">
          <form onSubmit={updateProfile} className="space-y-5">
            <span className={sectionLabel}>Profile</span>
            <Field label="Display name">
              <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="How should we greet you?" />
            </Field>
            <Button type="submit">Save profile</Button>
          </form>
        </section>

        <section className="border-t border-line py-8">
          <form onSubmit={changePassword} className="space-y-5">
            <span className={sectionLabel}>Password</span>
            <Field label="Current password">
              <Input
                type="password"
                autoComplete="current-password"
                value={passwordForm.currentPassword}
                onChange={(event) => setPasswordForm({ ...passwordForm, currentPassword: event.target.value })}
              />
            </Field>
            <Field label="New password" hint="At least 12 characters.">
              <Input
                type="password"
                minLength={12}
                autoComplete="new-password"
                value={passwordForm.newPassword}
                onChange={(event) => setPasswordForm({ ...passwordForm, newPassword: event.target.value })}
              />
            </Field>
            <Button type="submit">Change password</Button>
          </form>
        </section>

        <section className="border-t border-line py-8">
          <span className={sectionLabel}>Travel profile</span>
          <p className="text-sm leading-relaxed text-mist">
            Airports, budget, comfort rules — everything that powers your alerts.
          </p>
          <ButtonLink href="/onboarding" variant="secondary" className="mt-5">Retake the quiz</ButtonLink>
        </section>

        <section className="border-t border-line py-8">
          <span className={sectionLabel}>Plan &amp; billing</span>
          <p className="text-sm leading-relaxed text-mist">
            {billing?.plan === "pro"
              ? "Manage your subscription and invoices through the Stripe billing portal."
              : "You're on the free plan. Pro unlocks more watches, more AI searches, and weekly digests."}
          </p>
          <div className="mt-5">
            {billing?.canManageBilling ? (
              <Button variant="secondary" onClick={() => void manageBilling()}>Manage billing</Button>
            ) : (
              <ButtonLink href="/pricing" variant="secondary">View pricing</ButtonLink>
            )}
          </div>
        </section>

        {/* GDPR rights get real presence: a brand promise, not a legal appendix. */}
        <section className="border-t border-line py-8">
          <span className={sectionLabel}>Your data</span>
          <p className="max-w-lg text-sm leading-relaxed text-mist">
            Your data lives in the EU and belongs to you. Download everything we hold about you as a
            single file, or permanently erase your account and all its data — no questions, no retention
            tricks. Details in the{" "}
            <a href="/privacy" className="text-mint underline hover:text-cloud">privacy policy</a>.
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-6">
            <Button variant="secondary" onClick={() => void downloadData()}>
              Download everything we have
            </Button>
            <button
              type="button"
              onClick={() => void deleteAccount()}
              className="font-mono text-[11px] font-semibold uppercase tracking-label text-coral/80 transition-colors hover:text-coral"
            >
              Delete my account
            </button>
          </div>
        </section>

        <section className="border-t border-line py-8">
          <Button
            variant="secondary"
            onClick={() => {
              void logout().then(() => {
                window.location.href = "/";
              });
            }}
          >
            Log out
          </Button>
        </section>
      </div>
    </AppShell>
  );
}
