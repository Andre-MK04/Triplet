import type { Metadata } from "next";

import { apiBaseUrl } from "../../../lib/api";
import { tripPreviewDescription, tripPreviewTitle } from "../../../lib/tripPreview";
import type { TripOption } from "../../../lib/types";
import { TripDetailClient } from "./client";

/**
 * Trip suggestions expire, so they are never indexed — an indexed one becomes a
 * search result promising a fare that no longer exists. Social previews still
 * work: `noindex` keeps it out of search results without stopping a link shared
 * in a message from unfurling, which is how these URLs actually travel.
 */

const FALLBACK: Metadata = {
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

type SuggestionResponse = { trip?: TripOption };

/**
 * Build the preview from the suggestion itself, when it is one anybody may see.
 *
 * Fetched without credentials on purpose. The endpoint returns anonymous
 * suggestions to anyone holding the link and refuses user-owned ones, so an
 * unauthenticated request is exactly the visibility a stranger following a
 * shared link would have — a private trip yields the generic preview rather
 * than leaking a route and a price into a chat app.
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;

  try {
    const response = await fetch(
      `${apiBaseUrl}/trips/suggestions/${encodeURIComponent(id)}`,
      // Suggestions expire; a cached preview would outlive the thing it
      // describes. Short-lived caching keeps repeated unfurls off the API
      // without letting a stale fare persist.
      { next: { revalidate: 300 } },
    );
    if (!response.ok) return FALLBACK;

    const body = (await response.json()) as SuggestionResponse;
    const trip = body.trip;
    if (!trip?.outboundFlight) return FALLBACK;

    const title = tripPreviewTitle(trip);
    const description = tripPreviewDescription(trip);

    return {
      ...FALLBACK,
      title,
      description,
      openGraph: { title, description, type: "website" },
      twitter: { card: "summary_large_image", title, description },
    };
  } catch {
    // A preview is a nicety; the page must open whether or not the API answers.
    return FALLBACK;
  }
}

export default async function TripDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TripDetailClient suggestionId={id} />;
}
