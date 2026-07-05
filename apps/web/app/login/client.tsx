"use client";

import { AppShell } from "../../components/AppShell";
import { AuthForm } from "../../components/AuthForm";

export function LoginClient() {
  return (
    <AppShell>
      <AuthForm mode="login" />
    </AppShell>
  );
}
