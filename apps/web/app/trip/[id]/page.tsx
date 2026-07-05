import { TripDetailClient } from "./client";

export default async function TripDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TripDetailClient suggestionId={id} />;
}
