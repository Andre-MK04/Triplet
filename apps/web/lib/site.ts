/**
 * The canonical public origin, for absolute URLs in metadata.
 *
 * Falls back to localhost so a development build produces something valid
 * rather than "undefined/sitemap.xml" — set NEXT_PUBLIC_SITE_URL in production.
 */
export function siteUrl(): string {
  const configured = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  // Farelin is the canonical identity even on a Vercel preview. Falling back
  // to VERCEL_PROJECT_PRODUCTION_URL would revive the old triplet-web hostname
  // whenever one environment variable was omitted.
  if (process.env.NODE_ENV === "production") return "https://www.farelin.com";
  return "http://localhost:3001";
}
