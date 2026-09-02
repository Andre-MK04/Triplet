"use client";

import { useEffect, useRef, useState } from "react";

import { AppShell } from "../../../components/AppShell";
import { ButtonLink } from "../../../components/ui/Button";
import { Spinner } from "../../../components/ui/Misc";
import { ApiError, apiPost } from "../../../lib/api";
import { airportCity } from "../../../lib/airports";
import { formatPrice } from "../../../lib/format";
import type { SavedSearch } from "../../../lib/types";

/**
 * Where an emailed watch becomes a real one.
 *
 * Confirmation is a POST fired from the page rather than work done by the link
 * itself. Corporate mail scanners and link previewers routinely follow URLs in
 * incoming mail, and the token is single-use — so a GET that confirmed on
 * arrival would let a scanner burn the traveller's link before they ever
 * clicked it. A POST from script is not something a prefetcher performs.
 */

type State =
  | { status: "confirming" }
  | { status: "confirmed"; watch: SavedSearch }
  | {
      status: "failed";
      title: string;
      detail: string;
      canRetry: boolean;
      /** False when a watch may in fact be active, so we must not claim otherwise. */
      nothingWasSetUp: boolean;
    };

const MISSING_TOKEN: State = {
  status: "failed",
  title: "This link is incomplete.",
  detail:
    "The confirmation link needs the token from your email. Try opening the link again, or copy the whole address across if your mail client split it over two lines.",
  canRetry: false,
  nothingWasSetUp: true,
};

/**
 * A plain-language summary of what was just switched on.
 *
 * Every field is treated as optional and skipped when absent: this renders
 * whatever the API returned, and a summary missing a line is far better than a
 * confirmation page that throws on "undefined–undefined nights".
 */
function describe(watch: SavedSearch): string[] {
  const lines: string[] = [];

  const airports = watch.originAirports ?? [];
  if (airports.length > 0) {
    const shown = airports.slice(0, 4).map((code) => airportCity(code) || code);
    const remaining = airports.length - shown.length;
    lines.push(
      `Flying from ${shown.join(", ")}${remaining > 0 ? ` and ${remaining} more` : ""}`,
    );
  }
  if (typeof watch.maxBudget === "number") {
    lines.push(`Up to ${formatPrice(watch.maxBudget)} per trip`);
  }
  if (
    typeof watch.minTripLengthDays === "number" &&
    typeof watch.maxTripLengthDays === "number"
  ) {
    lines.push(`${watch.minTripLengthDays}–${watch.maxTripLengthDays} nights`);
  }
  if (watch.frequency) lines.push(`Checked ${watch.frequency}`);

  return lines;
}

export function WatchConfirmClient() {
  const [state, setState] = useState<State>({ status: "confirming" });
  // The token is single-use. React runs effects twice in development, and a
  // second POST would consume nothing and report the link as already used —
  // making a working confirmation look broken to anyone developing this page.
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;

    // Read from the live URL rather than useSearchParams so a token containing
    // characters a mail client may have re-encoded still arrives intact.
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setState(MISSING_TOKEN);
      return;
    }

    // Deliberately no cancellation flag here. The ref above already guarantees
    // exactly one request, and React re-runs effects in development: a cleanup
    // that cancelled would silence the only response in flight — the second run
    // returns early at the guard and never restarts it — leaving the page
    // spinning forever. Settling state after an unmount is a no-op in React 18.
    apiPost<SavedSearch>(`/alerts/verify?token=${encodeURIComponent(token)}`)
      .then((watch) => setState({ status: "confirmed", watch }))
      .catch((error: unknown) => setState(failureFor(error)));
  }, []);

  if (state.status === "confirming") {
    return (
      <AppShell>
        <div className="flex flex-col items-center gap-4 py-32">
          <Spinner label="Confirming your watch…" />
          <p className="font-mono text-[11px] uppercase tracking-label text-mist-dim">
            Checking your link
          </p>
        </div>
      </AppShell>
    );
  }

  if (state.status === "failed") {
    return (
      <AppShell>
        <div className="mx-auto max-w-md py-24 text-center">
          <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-coral">
            Not confirmed
          </p>
          <h1 className="font-display text-3xl font-bold text-cloud">{state.title}</h1>
          <p className="mt-3 text-sm leading-relaxed text-mist">{state.detail}</p>
          <div className="mt-8 flex justify-center gap-4">
            <ButtonLink href="/discover">
              {state.canRetry ? "Set the watch up again" : "Search for trips"}
            </ButtonLink>
            <ButtonLink href="/" variant="secondary">
              Back home
            </ButtonLink>
          </div>
          {state.nothingWasSetUp ? (
            <p className="mt-6 text-xs leading-relaxed text-mist-dim">
              Nothing was set up, and Triplet will not email that address.
            </p>
          ) : null}
        </div>
      </AppShell>
    );
  }

  const { watch } = state;
  return (
    <AppShell>
      <div className="mx-auto max-w-md py-24 text-center">
        <p className="mb-3 font-mono text-[11px] font-semibold uppercase tracking-label text-mint">
          Watch confirmed
        </p>
        <h1 className="font-display text-3xl font-bold text-cloud">
          Triplet is now watching this search.
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-mist">
          We&apos;ll email {watch.email} when a trip worth your attention turns up. Prices are
          fares Triplet has observed, so check the live price before you book.
        </p>

        <dl className="mt-8 border-y border-line py-5 text-left">
          {describe(watch).map((line) => (
            <div key={line} className="flex gap-3 py-1.5">
              <span aria-hidden className="font-mono text-xs leading-relaxed text-mint">
                ·
              </span>
              <dd className="text-sm leading-relaxed text-mist">{line}</dd>
            </div>
          ))}
        </dl>

        <div className="mt-8 flex justify-center gap-4">
          <ButtonLink href="/discover">Find more trips</ButtonLink>
          <ButtonLink href="/signup" variant="secondary">
            Create an account
          </ButtonLink>
        </div>
        <p className="mt-6 text-xs leading-relaxed text-mist-dim">
          Every email carries an unsubscribe link, and the manage link from your confirmation
          email still works. With an account you can see all your watches in one place.
        </p>
      </div>
    </AppShell>
  );
}

function failureFor(error: unknown): State {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return {
        status: "failed",
        // 404 covers both a wrong token and an already-spent one, and the API
        // deliberately does not distinguish them. Say so plainly rather than
        // guessing, since "already confirmed" is the likelier and happier case.
        title: "This link has already been used.",
        detail:
          "Confirmation links work once. If you already confirmed this watch, it is active and there is nothing more to do. If you never confirmed it, set the watch up again to get a fresh link.",
        canRetry: true,
        // A spent token most often means a confirmed, running watch.
        nothingWasSetUp: false,
      };
    }
    if (error.status === 400) {
      return {
        status: "failed",
        title: "This link has expired.",
        detail:
          "Confirmation links are short-lived so an old email cannot switch on a watch long after the fact. Set the watch up again and we will send a new one.",
        canRetry: true,
        nothingWasSetUp: true,
      };
    }
    if (error.status === 429) {
      return {
        status: "failed",
        title: "Too many attempts.",
        detail: "Wait a minute and open the link again.",
        canRetry: false,
        nothingWasSetUp: false,
      };
    }
  }
  return {
    status: "failed",
    title: "We couldn't reach Triplet.",
    detail:
      "The confirmation didn't go through. Your link is still good — open it again in a moment.",
    canRetry: false,
    // The request may or may not have landed; do not assert either way.
    nothingWasSetUp: false,
  };
}
