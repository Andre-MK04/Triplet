import type { MetadataRoute } from "next";

import { siteUrl } from "../lib/site";

/**
 * Only stable public pages.
 *
 * Nothing user-specific and nothing that expires: a sitemap is a promise that a
 * URL is worth fetching again, which a trip suggestion cannot keep.
 *
 * No `lastModified`. It used to be `new Date()` on every entry, which told
 * crawlers that all eight pages had changed at the moment the sitemap was
 * generated — every single time it was generated. That is not a freshness
 * signal, it is noise, and a crawler that learns the dates are meaningless
 * stops believing them. Omitting the field says nothing rather than something
 * false; if these pages ever get real revision tracking, the honest date can
 * go here then.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const base = siteUrl();

  return [
    { url: base, changeFrequency: "daily", priority: 1 },
    { url: `${base}/discover`, changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/pricing`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${base}/login`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/signup`, changeFrequency: "yearly", priority: 0.4 },
    { url: `${base}/privacy`, changeFrequency: "monthly", priority: 0.3 },
    { url: `${base}/terms`, changeFrequency: "monthly", priority: 0.3 },
    { url: `${base}/security`, changeFrequency: "monthly", priority: 0.3 },
  ];
}
