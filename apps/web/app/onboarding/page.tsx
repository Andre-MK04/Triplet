import type { Metadata } from "next";

import { OnboardingClient } from "./client";

export const metadata: Metadata = { title: "Your travel profile", robots: { index: false, follow: false } };

export default function OnboardingPage() {
  return <OnboardingClient />;
}
