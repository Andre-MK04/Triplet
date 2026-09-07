import { siteUrl } from "./site";

const publicUrl = siteUrl();

/**
 * Farelin's public identity.
 *
 * Internal Triplet identifiers remain intentionally untouched for deployment
 * and database compatibility. User-facing code should import this object
 * instead of creating another product-name or production-URL literal.
 */
export const BRAND = {
  name: "Farelin",
  tagline: "Find cheap trips, not just cheap flights",
  url: publicUrl,
  domain: new URL(publicUrl).hostname,
  supportEmail: "hello@farelin.com",
} as const;
