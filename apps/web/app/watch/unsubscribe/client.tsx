"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../../components/AppShell";
import { Button, ButtonLink } from "../../../components/ui/Button";
import { apiPost } from "../../../lib/api";

type Credentials = { watchId: string; token: string };
type State = "ready" | "working" | "done" | "invalid" | "error";

export function WatchUnsubscribeClient() {
  const [credentials, setCredentials] = useState<Credentials | null>(null);
  const [state, setState] = useState<State>("ready");

  useEffect(() => {
    // Tokens are delivered in the URL fragment so browsers, proxies and server
    // access logs never receive them. Query parsing remains as a compatibility
    // fallback for links generated before this page shipped.
    const params = new URLSearchParams(
      window.location.hash ? window.location.hash.slice(1) : window.location.search,
    );
    const watchId = params.get("watch");
    const token = params.get("token");
    window.history.replaceState({}, "", "/watch/unsubscribe");
    if (!watchId || !token) {
      setState("invalid");
      return;
    }
    setCredentials({ watchId, token });
  }, []);

  async function unsubscribe() {
    if (!credentials) return;
    setState("working");
    try {
      await apiPost(`/alerts/${encodeURIComponent(credentials.watchId)}/unsubscribe`, {
        token: credentials.token,
      });
      setCredentials(null);
      setState("done");
    } catch {
      setState("error");
    }
  }

  const copy =
    state === "done"
      ? {
          eyebrow: "Watch stopped",
          title: "You will not receive more emails for this watch.",
          detail: "Other Farelin watches are unchanged.",
        }
      : state === "invalid"
        ? {
            eyebrow: "Invalid link",
            title: "This unsubscribe link is incomplete.",
            detail: "Open the complete link from your Farelin email, or manage signed-in watches from your dashboard.",
          }
        : state === "error"
          ? {
              eyebrow: "Could not unsubscribe",
              title: "The link may be invalid or the service may be temporarily unavailable.",
              detail: "Try the link again shortly. If it still fails, contact Farelin and we will stop the watch for you.",
            }
          : {
              eyebrow: "Email preferences",
              title: "Stop emails for this watch?",
              detail: "This only disables the watch linked from your email. It does not delete your Farelin account or affect other watches.",
            };

  return (
    <AppShell>
      <main className="mx-auto max-w-lg py-24 text-center">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
          {copy.eyebrow}
        </p>
        <h1 className="mt-3 font-display text-3xl font-bold text-cloud">{copy.title}</h1>
        <p className="mt-4 text-sm leading-relaxed text-mist">{copy.detail}</p>
        <div className="mt-8 flex flex-wrap justify-center gap-4">
          {credentials && state !== "done" ? (
            <Button variant="danger" disabled={state === "working"} onClick={() => void unsubscribe()}>
              {state === "working" ? "Stopping watch…" : "Unsubscribe this watch"}
            </Button>
          ) : null}
          <ButtonLink href="/dashboard" variant="secondary">Go to dashboard</ButtonLink>
          {state === "error" ? <ButtonLink href="/contact" variant="ghost">Contact Farelin</ButtonLink> : null}
        </div>
      </main>
    </AppShell>
  );
}
