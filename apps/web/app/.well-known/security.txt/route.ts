import { siteUrl } from "../../../lib/site";

export const dynamic = "force-static";

export function GET() {
  const origin = siteUrl();
  const body = [
    `Contact: ${origin}/contact`,
    `Canonical: ${origin}/.well-known/security.txt`,
    "Preferred-Languages: en, sl",
    "Expires: 2027-09-01T00:00:00.000Z",
    `Policy: ${origin}/security`,
    "",
  ].join("\n");

  return new Response(body, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=86400",
    },
  });
}
