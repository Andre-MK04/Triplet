import type { NextConfig } from "next";
import path from "node:path";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

// When set (production), API calls go to a same-origin path (/backend/…) and Next
// proxies them here server-side. First-party cookies: browsers' third-party cookie
// blocking between vercel.app and railway.app can't break auth this way.
const apiProxyTarget = process.env.API_PROXY_TARGET;

// Farelin loads no third-party scripts. Affiliate commission is earned through
// the `marker` query parameter that the API puts into every Aviasales booking
// URL it builds (see providers/travelpayouts/affiliate_links.py), so the
// Travelpayouts Drive script was never what carried attribution — it was
// third-party behavioural JS on every page for nothing, with the power to
// rewrite outbound links. It is gone, and so is its CSP origin.
//
// Inline styles remain because React/Framer use them for calculated geometry.
// The fixed pre-paint theme script is an external same-origin asset. Next.js
// App Router still emits inline hydration bootstrap scripts in a static build,
// however, and this deployment has no per-request nonce pipeline. Removing
// script-src 'unsafe-inline' would block hydration. A nonce would require
// dynamic rendering/middleware across the app, so keep the narrower working
// policy and continue to prohibit third-party script hosts and unsafe-eval in
// production.
const isDev = process.env.NODE_ENV !== "production";
// NODE_ENV is also "production" for a local `next start`. Vercel supplies
// VERCEL_ENV at build and runtime, so key HSTS to the actual public production
// environment rather than teaching localhost to remember an HTTPS policy.
const isProductionDeployment = process.env.VERCEL_ENV === "production";

const contentSecurityPolicy = [
  "default-src 'self'",
  // A relative API base (proxy mode) is already covered by 'self'.
  `connect-src 'self'${apiBaseUrl.startsWith("http") ? " " + apiBaseUrl : ""}`,
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  ...(isProductionDeployment
    ? [{ key: "Strict-Transport-Security", value: "max-age=31536000" }]
    : []),
];

const nextConfig: NextConfig = {
  outputFileTracingRoot: path.join(__dirname, "../.."),
  async redirects() {
    return [
      {
        source: "/:path*",
        has: [{ type: "host", value: "triplet-web.vercel.app" }],
        destination: "https://www.farelin.com/:path*",
        permanent: true,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: securityHeaders,
      },
    ];
  },
  async rewrites() {
    if (!apiProxyTarget) return [];
    return [
      {
        source: "/backend/:path*",
        destination: `${apiProxyTarget.replace(/\/$/, "")}/:path*`,
      },
    ];
  },
};

export default nextConfig;
