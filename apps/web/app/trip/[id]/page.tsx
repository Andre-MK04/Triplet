import type { Metadata } from "next";

import { TripDetailClient } from "./client";

/**
 * Trip suggestions expire, so they are never indexed — an indexed one becomes a
 * search result promising a fare that no longer exists. Social previews still
 * work: `noindex` keeps it out of search results without stopping a link shared
 * in a message from unfurling, which is how these URLs actually travel.
 */
export const metadata: Metadata = {
  title: "Trip details",
  description: "A trip Triplet found, with every flight, date and observed fare.",
  robots: { index: false, follow: false },
  openGraph: {
    title: "A trip on Triplet",
    description: "Every flight, date and observed fare — check the live price before booking.",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

export default async function TripDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TripDetailClient suggestionId={id} />;
}
