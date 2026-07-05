"use client";

import { AppShell } from "../../components/AppShell";
import { AuthForm } from "../../components/AuthForm";

export function SignupClient() {
  return (
    <AppShell>
      <AuthForm mode="signup" />
    </AppShell>
  );
}
