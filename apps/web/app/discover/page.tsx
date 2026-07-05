import type { Metadata } from "next";
import { Suspense } from "react";

import { DiscoverClient } from "./client";

export const metadata: Metadata = { title: "Discover trips" };

export default function DiscoverPage() {
  return (
    <Suspense>
      <DiscoverClient />
    </Suspense>
  );
}
