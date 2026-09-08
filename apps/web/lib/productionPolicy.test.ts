import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("production publication controls", () => {
  it("serves security.txt with canonical same-origin contact and policy links", () => {
    const source = read("../app/.well-known/security.txt/route.ts");

    expect(source).toContain("Contact: ${origin}/contact");
    expect(source).toContain("Canonical: ${origin}/.well-known/security.txt");
    expect(source).toContain("Policy: ${origin}/security");
    expect(source).toContain("Preferred-Languages: en, sl");
    expect(source).toContain("Expires:");
  });

  it("keeps login and signup out of the sitemap and explicitly noindexes them", () => {
    const sitemap = read("../app/sitemap.ts");
    const login = read("../app/login/page.tsx");
    const signup = read("../app/signup/page.tsx");

    expect(sitemap).not.toContain("`${base}/login`");
    expect(sitemap).not.toContain("`${base}/signup`");
    expect(login).toContain("index: false");
    expect(signup).toContain("index: false");
  });

  it("gets displayed legal versions from the backend source of truth", () => {
    const terms = read("../app/terms/client.tsx");
    const privacy = read("../app/privacy/client.tsx");

    expect(terms).toContain("useLegalVersions()");
    expect(terms).not.toContain("const LAST_UPDATED");
    expect(privacy).toContain("useLegalVersions()");
    expect(privacy).not.toContain("const LAST_UPDATED");
  });

  it("loads the fixed theme initializer while documenting Next hydration's CSP constraint", () => {
    const config = read("../next.config.ts");
    const layout = read("../app/layout.tsx");

    expect(layout).toContain('src="/theme-init.js"');
    expect(layout).not.toContain("dangerouslySetInnerHTML");
    expect(config).toContain("App Router still emits inline hydration bootstrap scripts");
    expect(config).toContain('isDev ? " \'unsafe-eval\'" : ""');
  });

  it("only sends frontend HSTS from the real Vercel production environment", () => {
    const config = read("../next.config.ts");

    expect(config).toContain('process.env.VERCEL_ENV === "production"');
    expect(config).toContain("isProductionDeployment");
  });
});
