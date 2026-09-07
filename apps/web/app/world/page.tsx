import { TravelMapClient } from "./client";

export const metadata = {
  title: "My World",
  description: "Keep track of the countries you have visited, lived in, and want to explore next.",
};

export default function WorldPage() {
  return <TravelMapClient />;
}
