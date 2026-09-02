"use client";

import { useEffect, useRef, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { ButtonLink, Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Misc";
import { apiPost } from "../../lib/api";

/**
 * Where an emailed confirmation link becomes a verified account.
 *
 * A POST, not a GET, for the same reason the watch confirmation page is:
 * corporate mail scanners and link previewers follow URLs in incoming mail,
 * and the token is single-use — so a link that verified on arrival could be
 * spent by a scanner before the person ever clicked it.
 */

type State =
  | { status: "verifying" }
  | { status: "verified" }
  | { status: "failed"; detail: string };

const MISSING_TOKEN: State = {
  status: "failed",
  detail:
    "This confirmation link is incomplete. Open the link from your email again, or copy the whole address across if your mail client split it over two lines.",
};

export function VerifyEmailClient() {
  const { user, refresh } = useAuth();
  const [state, setState] = useState<State>({ status: "verifying" });
  const [resent, setResent] = useState(false);
  // The token is single-use and React runs effects twice in development; a
  // second POST would spend nothing and report a working link as broken.
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;

    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setState(MISSING_TOKEN);
      return;
    }

    // No cancellation flag: the ref above already guarantees one request, and
    // cancelling on cleanup would discard the only response in flight.
    apiPost("/auth/verify-email", { token })
      .then(() => {
        setState({ status: "verified" });
        // Pull the session again so the rest of the app stops showing the
        // "not confirmed" notice without needing a reload.
        void refresh?.();
      })
      .catch((error: unknown) => {
        const detail =
          error instanceof Error && error.message
            ? error.message
            : "This confirmation link is no longer valid.";
        setState({ status: "failed", detail });
      });
  }, [refresh]);

  async function resend() {
    try {
      await apiPost("/auth/verify-email/resend");
    } catch {
      // The endpoint answers the same way whatever happens; a network failure
      // here should not contradict that with a different story.
    }
    setResent(true);
  }

  if (state.status === "verifying") {
    return (
      <AppShell>
        <div className="flex flex-col items-center gap-4 py-32">
          <Spinner label="Confirming your email…" />
          <p className="font-mono text-[11px] uppercase tracking-label text-mist-dim">
            Checking your link
          </p>
        </div>
      </AppShell>
    );
  }

  if (state.status === "verified") {
    return (
      <AppShell>
        <div className="mx-auto max-w-md py-24 text-center">
          <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
            Email confirmed
          </p>
          <h1 className="font-display text-3xl font-bold text-cloud">
            That address is confirmed.
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-mist">
            Triplet can now send fare alerts to it, and watches you set on this account
            will not need confirming separately.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <ButtonLink href="/discover">Find trips</ButtonLink>
            <ButtonLink href="/account" variant="secondary">
              Your account
            </ButtonLink>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-md py-24 text-center">
        <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-coral">
          Not confirmed
        </p>
        <h1 className="font-display text-3xl font-bold text-cloud">
          This link is no longer valid.
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-mist">{state.detail}</p>
        <p className="mt-3 text-sm leading-relaxed text-mist">
          Confirmation links work once and expire after a day. If you already confirmed
          this address, there is nothing left to do.
        </p>

        <div className="mt-8 flex flex-col items-center gap-4">
          {user ? (
            resent ? (
              <p className="text-sm text-mint" role="status">
                If that address still needs confirming, a new link is on its way.
              </p>
            ) : (
              <Button onClick={resend}>Send another link</Button>
            )
          ) : (
            <p className="text-sm leading-relaxed text-mist-dim">
              Log in and Triplet can send you a fresh link.
            </p>
          )}
          <div className="flex justify-center gap-4">
            <ButtonLink href={user ? "/account" : "/login"} variant="secondary">
              {user ? "Your account" : "Log in"}
            </ButtonLink>
            <ButtonLink href="/" variant="secondary">
              Back home
            </ButtonLink>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
