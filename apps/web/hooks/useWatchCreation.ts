"use client";

import { FormEvent, useEffect, useState } from "react";

import { apiGet, apiPost } from "../lib/api";
import { limitAwareError } from "../lib/discoverMessages";
import { formatPrice } from "../lib/format";
import { watchDefaultsForPreference } from "../lib/notificationPreferences";
import type { AuthUser, SavedSearch, TravelProfile, TripSearchPayload } from "../lib/types";
import type { WatchTriggerMode } from "../lib/watchTriggers";

/**
 * Turning the search on screen into a watch.
 *
 * Its own hook because none of this state means anything to the rest of
 * Discover: the form fields, what happened when it was submitted, and the watch
 * that came back are only ever read by the form itself.
 *
 * The one thing outside it needs is the search being watched, which is passed
 * in rather than held here — a watch is created from a search, so the search is
 * the input, not shared state.
 */
export function useWatchCreation(
  user: AuthUser | null,
  lastPayload: TripSearchPayload | null,
) {
  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [frequency, setFrequency] = useState<"daily" | "weekly">("daily");
  // What is worth an email, as opposed to how often one may arrive. Two
  // different questions that were previously one setting on the account.
  const [trigger, setTrigger] = useState<WatchTriggerMode>("any");
  const [status, setStatus] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState<SavedSearch | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    Promise.all([
      apiGet<TravelProfile>("/me/travel-profile"),
      apiGet<{ limits?: { allowedAlertFrequencies?: string[] } }>("/billing/status"),
    ])
      .then(([profile, billing]) => {
        if (cancelled) return;
        const defaults = watchDefaultsForPreference(
          profile.notificationFrequency,
          billing.limits?.allowedAlertFrequencies ?? ["weekly"],
        );
        setFrequency(defaults.frequency);
        setTrigger(defaults.trigger);
      })
      .catch(() => {
        // Keep conservative local defaults. The backend remains authoritative.
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!lastPayload) {
      setStatus({ tone: "error", text: "Run a search first so we know what to watch." });
      return;
    }
    if (
      lastPayload.destinationCountries?.length ||
      lastPayload.destinationRegions?.length ||
      lastPayload.destinationContinents?.length ||
      lastPayload.excludeEurope ||
      lastPayload.unvisitedOnly
    ) {
      setStatus({
        tone: "error",
        text: "Country and region watches are not available yet. Choose a city or airport, or use an anywhere search.",
      });
      return;
    }

    setIsSaving(true);
    setStatus(null);
    try {
      const body = {
        ...lastPayload,
        email: user?.email ?? email,
        name:
          name ||
          `${lastPayload.originAirports.slice(0, 3).join("/")} under ${formatPrice(lastPayload.maxBudget)}`,
        frequency,
        triggerMode: trigger,
      };
      const data = await apiPost<SavedSearch>(user ? "/me/saved-searches" : "/alerts", body);
      setSaved(data);
      if (data.emailVerificationRequired && data.verificationEmailAccepted === false) {
        setStatus({
          tone: "error",
          text: "The watch was saved, but Farelin's mail service did not accept the confirmation email. Please try again after email delivery is configured.",
        });
      } else if (data.emailVerificationRequired) {
        setStatus({
          tone: "success",
          text: `Check ${data.email || email || "your email"} to confirm this watch. Farelin starts watching once you do.`,
        });
      } else {
        setStatus({
          tone: "success",
          text: "Saved! Farelin is now watching this search" + (user ? " — see it on your dashboard." : "."),
        });
      }
    } catch (saveError) {
      setStatus({ tone: "error", text: limitAwareError(saveError) });
    } finally {
      setIsSaving(false);
    }
  }

  async function resendVerification() {
    if (!saved?.verificationResendPath) return;
    setIsSaving(true);
    try {
      const result = await apiPost<{ deliveryAccepted: boolean }>(saved.verificationResendPath);
      setStatus(
        result.deliveryAccepted
          ? { tone: "success", text: `A fresh confirmation was accepted for ${saved.email}. Check spam if it does not arrive shortly.` }
          : { tone: "error", text: "Farelin's mail service did not accept a new confirmation message. Check the email setup before retrying." },
      );
    } catch (error) {
      setStatus({ tone: "error", text: limitAwareError(error) });
    } finally {
      setIsSaving(false);
    }
  }

  /**
   * Forget the last outcome, without forgetting what was typed.
   *
   * Called when a new search starts: a "watch saved" message left over from the
   * previous search would be describing something the traveller is no longer
   * looking at. The email and name stay, because they are still theirs.
   */
  function resetOutcome() {
    setStatus(null);
    setSaved(null);
  }

  return {
    isOpen,
    setIsOpen,
    name,
    setName,
    email,
    setEmail,
    frequency,
    setFrequency,
    trigger,
    setTrigger,
    status,
    isSaving,
    saved,
    save,
    resendVerification,
    resetOutcome,
  };
}
