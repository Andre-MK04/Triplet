import type { Metadata } from "next";
import { Suspense } from "react";

import { DiscoverClient } from "./client";

export const metadata: Metadata = {
  title: "Discover trips",
  description:
    "Describe the trip you want, or fine-tune every knob. Triplet builds complete trip ideas from real observed fares.",
};

// Server-rendered fallback: the heading and intro paint immediately, before the
// client bundle hydrates, so the page is never blank.
function DiscoverFallback() {
  return (
    <div className="mx-auto w-full max-w-6xl px-4 pt-8 sm:px-6">
      <header className="mb-8 max-w-2xl">
        <h1 className="font-display text-3xl font-bold text-cloud sm:text-4xl">Discover trips</h1>
        <p className="mt-2 text-mist">
          Describe the trip you want, or fine-tune every knob. Triplet builds complete trip ideas
          from real observed fares.
        </p>
      </header>
      <p className="border-y border-line py-10 text-center font-mono text-[11px] uppercase tracking-[0.12em] text-mist">
        Loading the search console…
      </p>
    </div>
  );
}

export default function DiscoverPage() {
  return (
    <Suspense fallback={<DiscoverFallback />}>
      <DiscoverClient />
    </Suspense>
  );
}
