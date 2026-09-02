import type { Metadata } from "next";

import { SignupClient } from "./client";

export const metadata: Metadata = {
  alternates: { canonical: "/signup" }, title: "Create account" };

export default function SignupPage() {
  return <SignupClient />;
}
