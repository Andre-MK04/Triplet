import type { Metadata } from "next";

import { PrivacyClient } from "./client";

export const metadata: Metadata = { title: "Privacy policy" };

export default function PrivacyPage() {
  return <PrivacyClient />;
}
