"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "../../../components/AppShell";
import { useAuth } from "../../../components/AuthContext";
import { ButtonLink } from "../../../components/ui/Button";
import { Spinner } from "../../../components/ui/Misc";

const FAILURE_MESSAGES: Record<string, string> = {
  oauth_failed: "Google sign-in didn't complete — no account was changed.",
  database_unavailable: "We couldn't reach the database to finish signing you in.",
};

export function AuthCallbackClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refresh } = useAuth();
  const [failed, setFailed] = useState<string | null>(null);

  const status = searchParams.get("auth") ?? "oauth_success";

  useEffect(() => {
    if (status !== "oauth_success") {
      setFailed(FAILURE_MESSAGES[status] ?? "Sign-in didn't complete.");
      return;
    }
    let cancelled = false;
    // Cookies are already set by the callback redirect; confirm the session,
    // then land the user somewhere useful.
    void refresh().then(() => {
      if (!cancelled) router.replace("/dashboard");
    });
    return () => {
      cancelled = true;
    };
  }, [status, refresh, router]);

  if (failed) {
    return (
      <AppShell>
        <div className="mx-auto max-w-md py-24 text-center">
          <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-coral">
            Sign-in failed
          </p>
          <h1 className="font-display text-3xl font-bold text-cloud">That didn&apos;t work.</h1>
          <p className="mt-3 text-sm leading-relaxed text-mist">{failed}</p>
          <div className="mt-8 flex justify-center gap-4">
            <ButtonLink href="/login">Try again</ButtonLink>
            <ButtonLink href="/" variant="secondary">
              Back home
            </ButtonLink>
          </div>
          <p className="mt-6 text-xs text-mist/70">
            Still stuck? You can always{" "}
            <Link href="/signup" className="text-mint underline hover:text-cloud">
              create an account with email
            </Link>
            .
          </p>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="flex flex-col items-center gap-4 py-32">
        <Spinner label="Signing you in…" />
        <p className="font-mono text-[10px] uppercase tracking-label text-mist/60">
          Confirming your session
        </p>
      </div>
    </AppShell>
  );
}
