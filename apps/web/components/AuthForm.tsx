"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { apiBaseUrl } from "../lib/api";
import { useAuth } from "./AuthContext";
import { TripletMark } from "./AppShell";
import { Button } from "./ui/Button";
import { Field, Input } from "./ui/Input";
import { Notice } from "./ui/Misc";

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
    <div className="mx-auto w-full max-w-md py-10">
      <div className="glass rounded-card p-7 shadow-deal">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <TripletMark size={34} />
          <h1 className="font-display text-2xl font-bold text-cloud">
            {mode === "signup" ? "Create your travel profile" : "Welcome back"}
          </h1>
          <p className="text-sm text-mist">
            {mode === "signup"
              ? "One account, all your airports and alerts."
              : "Log in to see your watches and trip ideas."}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
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

        <div className="my-5 flex items-center gap-3 text-xs text-mist/60">
          <span className="h-px flex-1 bg-line" /> or <span className="h-px flex-1 bg-line" />
        </div>

        <a
          href={`${apiBaseUrl}/auth/oauth/google/start`}
          className="flex w-full items-center justify-center gap-2 rounded-full border border-line bg-white/5 px-5 py-2.5 text-sm font-semibold text-cloud transition hover:border-mint/50"
        >
          <span aria-hidden>G</span> Continue with Google
        </a>

        <p className="mt-6 text-center text-sm text-mist">
          {mode === "signup" ? (
            <>Already have an account? <Link href="/login" className="font-semibold text-sky hover:text-cloud">Log in</Link></>
          ) : (
            <>New to Triplet? <Link href="/signup" className="font-semibold text-sky hover:text-cloud">Create an account</Link></>
          )}
        </p>
      </div>
    </div>
  );
}
