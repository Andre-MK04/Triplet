import type { Metadata } from "next";

import { PricingClient } from "./client";

export const metadata: Metadata = {
  title: "Pricing",
  description:
    "Triplet is free to start. Pro adds more origin airports, more watches and daily checks.",
  alternates: { canonical: "/pricing" },
};

export default function PricingPage() {
  return <PricingClient />;
}
