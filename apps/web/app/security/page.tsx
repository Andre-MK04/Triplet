import type { Metadata } from "next";

import { SecurityClient } from "./client";

export const metadata: Metadata = {
  alternates: { canonical: "/security" }, title: "Security & privacy" };

export default function SecurityPage() {
  return <SecurityClient />;
}
