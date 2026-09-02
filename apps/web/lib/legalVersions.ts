"use client";

import { useEffect, useState } from "react";

import { apiGet } from "./api";

/**
 * The document versions a new account must accept.
 *
 * Fetched, never written down here. Signup is validated against the backend's
 * value, so a copy in the frontend would not merely drift — it would start
 * rejecting every signup the moment the two disagreed, which is the kind of
 * outage that looks like a mystery.
 */
export type LegalVersions = { termsVersion: string; privacyVersion: string } | null;

export function useLegalVersions(): LegalVersions {
  const [versions, setVersions] = useState<LegalVersions>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<{ termsVersion?: string; privacyVersion?: string }>("/billing/plans")
      .then((plans) => {
        if (cancelled) return;
        if (plans.termsVersion && plans.privacyVersion) {
          setVersions({ termsVersion: plans.termsVersion, privacyVersion: plans.privacyVersion });
        }
      })
      .catch(() => {
        // Left null. The signup button stays usable and the backend returns a
        // readable message, rather than the form silently refusing to submit.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return versions;
}
