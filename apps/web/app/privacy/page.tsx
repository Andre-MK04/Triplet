import type { Metadata } from "next";

import { PrivacyClient } from "./client";

export const metadata: Metadata = {
  alternates: { canonical: "/privacy" }, title: "Privacy policy" };

export default function PrivacyPage() {
  return <PrivacyClient />;
}
