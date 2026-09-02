import type { Metadata } from "next";

import { TermsClient } from "./client";

export const metadata: Metadata = {
  alternates: { canonical: "/terms" },
  title: "Terms of service",
  description:
    "What Triplet does, what it does not do, and what the prices it shows actually mean.",
};

export default function TermsPage() {
  return <TermsClient />;
}
