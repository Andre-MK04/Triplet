"use client";

import { AppShell } from "../../../components/AppShell";
import { ButtonLink } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/Misc";

export default function BillingCancelPage() {
  return (
    <AppShell>
      <EmptyState
        icon="🧾"
        title="Checkout canceled"
        action={<ButtonLink href="/pricing" variant="secondary">Back to pricing</ButtonLink>}
      >
        No charge was made and nothing changed on your plan. You can upgrade to Pro anytime — the free
        plan keeps watching your saved searches in the meantime.
      </EmptyState>
    </AppShell>
  );
}
