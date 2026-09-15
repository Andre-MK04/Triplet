"use client";

import { useEffect, useState } from "react";

import { apiGet } from "../lib/api";
import type { OpportunityFeed } from "../lib/types";

/** Private, provider-free feed. Account identity invalidates the prior user's rows. */
export function useOpportunities(identity: string | null) {
  const [feed, setFeed] = useState<OpportunityFeed | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [loadedIdentity, setLoadedIdentity] = useState<string | null>(null);

  useEffect(() => {
    if (!identity) {
      setFeed(null);
      setLoadedIdentity(null);
      setStatus("idle");
      return;
    }
    let current = true;
    setFeed(null);
    setLoadedIdentity(null);
    setStatus("loading");
    apiGet<OpportunityFeed>("/me/opportunities")
      .then((data) => {
        if (!current) return;
        setFeed(data);
        setLoadedIdentity(identity);
        setStatus("ready");
      })
      .catch(() => {
        if (!current) return;
        setLoadedIdentity(identity);
        setStatus("error");
      });
    return () => { current = false; };
  }, [identity]);

  // Never render a previous account's private rows, even for the one render
  // before React's effect invalidates its old request.
  return { feed: identity === loadedIdentity ? feed : null, status: identity === loadedIdentity ? status : identity ? "loading" as const : "idle" as const };
}
