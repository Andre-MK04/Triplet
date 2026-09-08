import type { Metadata } from "next";

import { SignupClient } from "./client";

export const metadata: Metadata = {
  alternates: { canonical: "/signup" },
  robots: { index: false, follow: false },
  title: "Create account",
};

export default function SignupPage() {
  return <SignupClient />;
}
