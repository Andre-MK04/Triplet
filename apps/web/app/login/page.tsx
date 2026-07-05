import type { Metadata } from "next";

import { LoginClient } from "./client";

export const metadata: Metadata = { title: "Log in" };

export default function LoginPage() {
  return <LoginClient />;
}
