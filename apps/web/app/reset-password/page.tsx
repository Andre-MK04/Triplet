"use client";

import { FormEvent, useEffect, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { Button } from "../../components/ui/Button";
import { Field, Input } from "../../components/ui/Input";
import { Notice } from "../../components/ui/Misc";
import { apiPost } from "../../lib/api";

export default function ResetPassword() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [token, setToken] = useState("");

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  async function requestReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus(null);
    try {
      await apiPost("/auth/forgot-password", { email });
      setStatus({ tone: "success", text: "If that email exists, a reset link has been sent." });
    } catch {
      setStatus({ tone: "error", text: "Could not request a reset link." });
    }
  }

  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus(null);
    try {
      await apiPost("/auth/reset-password", { token, newPassword: password });
      setStatus({ tone: "success", text: "Password reset. You can log in now." });
    } catch {
      setStatus({ tone: "error", text: "Could not reset password. The link may have expired." });
    }
  }

  return (
    <AppShell>
      <div className="mx-auto w-full max-w-md py-10">
        <form onSubmit={token ? resetPassword : requestReset} className="glass rounded-card space-y-4 p-7 shadow-deal">
          <h1 className="font-display text-2xl font-bold text-cloud">
            {token ? "Set a new password" : "Reset your password"}
          </h1>
          {token ? (
            <Field label="New password" hint="At least 12 characters.">
              <Input
                type="password"
                required
                minLength={12}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>
          ) : (
            <Field label="Email">
              <Input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
              />
            </Field>
          )}
          <Button type="submit" className="w-full">
            {token ? "Reset password" : "Send reset link"}
          </Button>
          {status ? <Notice tone={status.tone}>{status.text}</Notice> : null}
        </form>
      </div>
    </AppShell>
  );
}
