"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { Badge } from "../../components/ui/Badge";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Field, Input } from "../../components/ui/Input";
import { EmptyState, Notice, Spinner } from "../../components/ui/Misc";
import { apiGet, apiPatch, apiPost } from "../../lib/api";

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

  return (
    <AppShell>
      <div className="mx-auto max-w-2xl space-y-5 pb-10">
        <h1 className="font-display text-3xl font-bold text-cloud">Account</h1>

        {status ? <Notice tone={status.tone}>{status.text}</Notice> : null}

        <Card>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-mist">Email</p>
              <p className="mt-1 font-semibold text-cloud">{user.email}</p>
            </div>
            <Badge tone={billing?.plan === "pro" ? "mint" : "neutral"}>
              {billing?.plan === "pro" ? "Triplet Pro" : "Free plan"}
            </Badge>
          </div>
        </Card>

        <Card>
          <form onSubmit={updateProfile} className="space-y-4">
            <h2 className="font-display text-lg font-bold text-cloud">Profile</h2>
            <Field label="Display name">
              <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="How should we greet you?" />
            </Field>
            <Button type="submit">Save profile</Button>
          </form>
        </Card>

        <Card>
          <form onSubmit={changePassword} className="space-y-4">
            <h2 className="font-display text-lg font-bold text-cloud">Password</h2>
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
        </Card>

        <Card>
          <h2 className="font-display text-lg font-bold text-cloud">Travel profile</h2>
          <p className="mt-2 text-sm text-mist">Airports, budget, comfort rules — everything that powers your alerts.</p>
          <ButtonLink href="/onboarding" variant="secondary" className="mt-4">Edit travel profile</ButtonLink>
        </Card>

        <div className="flex flex-wrap gap-3">
          {billing?.canManageBilling ? (
            <Button variant="secondary" onClick={() => void manageBilling()}>Manage billing</Button>
          ) : (
            <ButtonLink href="/pricing" variant="secondary">View pricing</ButtonLink>
          )}
          <Button
            variant="danger"
            onClick={() => {
              void logout().then(() => {
                window.location.href = "/";
              });
            }}
          >
            Log out
          </Button>
        </div>
      </div>
    </AppShell>
  );
}
