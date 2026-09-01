/**
 * The canonical public origin, for absolute URLs in metadata.
 *
 * Falls back to localhost so a development build produces something valid
 * rather than "undefined/sitemap.xml" — set NEXT_PUBLIC_SITE_URL in production.
 */
export function siteUrl(): string {
  const configured = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (configured) return configured.replace(/\/$/, "");
  if (process.env.VERCEL_PROJECT_PRODUCTION_URL) {
    return `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`;
  }
  return "http://localhost:3001";
}
