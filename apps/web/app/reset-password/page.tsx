"use client";

import { FormEvent, useEffect, useState } from "react";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

export default function ResetPassword() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [token, setToken] = useState("");

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  async function requestReset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("");
    const response = await fetch(`${apiBaseUrl}/auth/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    setStatus(response.ok ? "If that email exists, a reset link has been sent." : "Could not request a reset link.");
  }

  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("");
    const response = await fetch(`${apiBaseUrl}/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, newPassword: password }),
    });
    setStatus(response.ok ? "Password reset. You can log in now." : "Could not reset password.");
  }

  return (
    <main className="min-h-screen px-5 py-8 sm:px-8 lg:px-12">
      <section className="mx-auto max-w-md">
        <a className="text-sm font-semibold uppercase tracking-[0.22em] text-mint" href="/">
          TRIPLET
        </a>
        <form onSubmit={token ? resetPassword : requestReset} className="mt-8 rounded-lg border border-line bg-panel/90 p-5">
          <h1 className="text-2xl font-semibold text-white">{token ? "Set new password" : "Reset password"}</h1>
          {token ? (
            <label className="mt-5 block">
              <span className="mb-1.5 block text-sm font-medium text-slate-300">New password</span>
              <input
                type="password"
                required
                minLength={12}
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
              />
            </label>
          ) : (
            <label className="mt-5 block">
              <span className="mb-1.5 block text-sm font-medium text-slate-300">Email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-md border border-line bg-ink px-3 py-2.5 text-white outline-none ring-mint/40 focus:ring-2"
              />
            </label>
          )}
          <button type="submit" className="mt-5 w-full rounded-md bg-mint px-4 py-3 font-semibold text-ink">
            {token ? "Reset password" : "Send reset link"}
          </button>
          {status ? <p className="mt-3 text-sm text-slate-300">{status}</p> : null}
        </form>
      </section>
    </main>
  );
}
