"use client";

import { useEffect, useState } from "react";

import { AppShell } from "../../../components/AppShell";
import { useAuth } from "../../../components/AuthContext";
import { ButtonLink } from "../../../components/ui/Button";
import { EmptyState, Spinner } from "../../../components/ui/Misc";
import { apiGet } from "../../../lib/api";

type BillingStatus = { plan: string; subscriptionStatus: string };

export default function BillingSuccessPage() {
  const { refresh } = useAuth();
  const [state, setState] = useState<"checking" | "active" | "delayed">("checking");

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;

    async function checkSubscription() {
      try {
        const billing = await apiGet<BillingStatus>("/billing/status");
        if (cancelled) return;
        if (billing.plan === "pro" && billing.subscriptionStatus === "active") {
          await refresh();
          if (!cancelled) setState("active");
          return;
        }
      } catch {
        // A short webhook delay or transient request failure is handled by the
        // bounded retry below; the page never spins forever.
      }
      attempt += 1;
      if (attempt >= 8) {
        if (!cancelled) setState("delayed");
        return;
      }
      timer = setTimeout(() => void checkSubscription(), 1500);
    }

    void checkSubscription();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [refresh]);

  const title =
    state === "active"
      ? "Farelin Pro is active"
      : state === "delayed"
        ? "Confirmation is taking longer"
        : "Confirming your plan";

  return (
    <AppShell>
      <EmptyState
        title={title}
        action={<ButtonLink href="/dashboard">Open dashboard</ButtonLink>}
      >
        {state === "checking" ? (
          <Spinner label="Waiting for Stripe’s confirmation…" />
        ) : state === "active" ? (
          "Your subscription was confirmed and your Pro limits are ready."
        ) : (
          "Farelin has not received the signed subscription confirmation yet. If you completed Checkout, your dashboard will update when it arrives. You do not need to start another checkout."
        )}
      </EmptyState>
    </AppShell>
  );
}
