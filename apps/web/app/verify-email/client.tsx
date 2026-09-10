"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../components/AppShell";
import { useAuth } from "../../components/AuthContext";
import { ButtonLink, Button } from "../../components/ui/Button";
import { Spinner } from "../../components/ui/Misc";
import { apiPost } from "../../lib/api";

/**
 * Where an emailed confirmation link becomes a verified account.
 *
 * A POST, not a GET, for the same reason the watch confirmation page is:
 * corporate mail scanners and link previewers follow URLs in incoming mail.
 * The GET only presents a confirmation screen; a deliberate button press is
 * required before the single-use token is sent to the API.
 */

type State =
  | { status: "loading" }
  | { status: "ready"; token: string }
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
  const [state, setState] = useState<State>({ status: "loading" });
  const [resent, setResent] = useState(false);

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setState(MISSING_TOKEN);
      return;
    }

    // Do not spend the single-use token on page load. Mail security scanners
    // commonly open links before the recipient does; requiring a deliberate
    // button press keeps those previews from confirming the account.
    setState({ status: "ready", token });
  }, []);

  function verify(token: string) {
    setState({ status: "verifying" });
    apiPost("/auth/verify-email", { token })
      .then(() => {
        window.history.replaceState({}, "", "/verify-email");
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
  }

  async function resend() {
    try {
      await apiPost("/auth/verify-email/resend");
    } catch {
      // The endpoint answers the same way whatever happens; a network failure
      // here should not contradict that with a different story.
    }
    setResent(true);
  }

  if (state.status === "loading" || state.status === "verifying") {
    return (
      <AppShell>
        <div className="flex flex-col items-center gap-4 py-32">
          <Spinner
            label={state.status === "loading" ? "Checking your link…" : "Confirming your email…"}
          />
          <p className="font-mono text-[11px] uppercase tracking-label text-mist-dim">
            {state.status === "loading" ? "Preparing confirmation" : "One moment"}
          </p>
        </div>
      </AppShell>
    );
  }

  if (state.status === "ready") {
    return (
      <AppShell>
        <div className="mx-auto max-w-md py-24 text-center">
          <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
            Confirm your address
          </p>
          <h1 className="font-display text-3xl font-bold text-cloud">
            One last step.
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-mist">
            Confirm that this email belongs to you so Farelin can send your fare alerts.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <Button onClick={() => verify(state.token)}>Confirm my email</Button>
            <ButtonLink href="/account" variant="secondary">
              Not now
            </ButtonLink>
          </div>
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
            Farelin can now send fare alerts to it, and watches you set on this account
            will not need confirming separately.
          </p>
          {!user ? (
            <p className="mt-3 text-sm leading-relaxed text-mist-dim">
              Your mail app opened this outside your Farelin session. Your address is
              confirmed; log in to continue.
            </p>
          ) : null}
          <div className="mt-8 flex justify-center gap-4">
            <ButtonLink href={user ? "/discover" : "/login"}>
              {user ? "Find trips" : "Log in"}
            </ButtonLink>
            {user ? (
              <ButtonLink href="/account" variant="secondary">
                Your account
              </ButtonLink>
            ) : null}
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
              Log in and Farelin can send you a fresh link.
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
