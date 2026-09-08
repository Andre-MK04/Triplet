import type { Metadata } from "next";

import { LoginClient } from "./client";

export const metadata: Metadata = {
  alternates: { canonical: "/login" },
  robots: { index: false, follow: false },
  title: "Log in",
};

export default function LoginPage() {
  return <LoginClient />;
}
