"use client";

import { AppShell } from "../../../components/AppShell";
import { ButtonLink } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/Misc";

export default function BillingSuccessPage() {
  return (
    <AppShell>
      <EmptyState
        icon="🎉"
        title="Checkout complete"
        action={<ButtonLink href="/dashboard">Open dashboard</ButtonLink>}
      >
        Welcome to Triplet Pro! Your subscription status will update as soon as Stripe sends the
        confirmation webhook — usually within seconds.
      </EmptyState>
    </AppShell>
  );
}
