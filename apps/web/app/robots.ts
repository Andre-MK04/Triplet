import type { MetadataRoute } from "next";

import { siteUrl } from "../lib/site";

/**
 * Public pages are indexable; anything personal or ephemeral is not.
 *
 * Trip suggestions expire, so an indexed one becomes a search result promising
 * a fare that no longer exists — worse for a traveller than not being found at
 * all. Account, dashboard and world pages are personal, and confirmation links
 * are single-use secrets.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/account",
        "/dashboard",
        "/onboarding",
        "/world",
        "/trip/",
        "/watch/",
        "/auth/",
        "/reset-password",
        "/backend/",
      ],
    },
    sitemap: `${siteUrl()}/sitemap.xml`,
  };
}
