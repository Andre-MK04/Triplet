"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { apiBaseUrl } from "../lib/api";
import { useAuth } from "./AuthContext";
import { Button } from "./ui/Button";
import { Field, Input } from "./ui/Input";
import { Notice } from "./ui/Misc";

const RouteGlobe = dynamic(() => import("./RouteGlobe"), { ssr: false });

export function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const { login, signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    try {
      if (mode === "signup") {
        await signup(email, password, displayName);
        router.push("/onboarding");
      } else {
        await login(email, password);
        router.push("/discover");
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Something went wrong.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    // Off-axis: the form takes the left third; a dim, slow globe fills the rest.
    <div className="relative grid items-center gap-12 py-14 lg:min-h-[70vh] lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
      <div className="relative z-10 w-full max-w-sm">
        <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
          {mode === "signup" ? "New account" : "Welcome back"}
        </p>
        <h1 className="font-display text-3xl font-bold text-cloud">
          {mode === "signup" ? "Create your travel profile." : "Log in to Triplet."}
        </h1>
        <p className="mt-2 text-sm text-mist">
          {mode === "signup"
            ? "One account, all your airports and alerts."
            : "Your watches and trip ideas are waiting."}
        </p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          {mode === "signup" ? (
            <Field label="Name (optional)">
              <Input
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                autoComplete="name"
                placeholder="How should we greet you?"
              />
            </Field>
          ) : null}
          <Field label="Email">
            <Input
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
            />
          </Field>
          <Field label="Password" hint={mode === "signup" ? "At least 12 characters." : undefined}>
            <Input
              type="password"
              required
              minLength={mode === "signup" ? 12 : undefined}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              placeholder="••••••••••••"
            />
          </Field>

          {error ? <Notice tone="error">{error}</Notice> : null}

          <Button type="submit" disabled={isSubmitting} className="w-full" size="lg">
            {isSubmitting ? "One moment…" : mode === "signup" ? "Create account" : "Log in"}
          </Button>
        </form>

        <div className="my-6 flex items-center gap-3 font-mono text-[10px] uppercase tracking-label text-mist/60">
          <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
        </div>

        <a
          href={`${apiBaseUrl}/auth/oauth/google/start`}
          className="flex w-full items-center justify-center gap-2 border border-line px-5 py-3 font-mono text-[11px] font-semibold uppercase tracking-label text-cloud transition-colors hover:border-mint/60 hover:text-mint"
        >
          Continue with Google
        </a>

        <p className="mt-8 text-sm text-mist">
          {mode === "signup" ? (
            <>
              Already have an account?{" "}
              <Link href="/login" className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint hover:text-cloud">
                Log in →
              </Link>
            </>
          ) : (
            <>
              New to Triplet?{" "}
              <Link href="/signup" className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint hover:text-cloud">
                Create an account →
              </Link>
              <span className="mt-2 block">
                <Link href="/reset-password" className="text-xs text-mist/70 underline hover:text-cloud">
                  Forgot password?
                </Link>
              </span>
            </>
          )}
        </p>
      </div>

      <div className="pointer-events-none relative hidden h-[540px] opacity-50 lg:block" aria-hidden>
        <div className="absolute -right-40 top-1/2 aspect-square h-[120%] -translate-y-1/2">
          <RouteGlobe interactive={false} />
        </div>
      </div>
    </div>
  );
}
