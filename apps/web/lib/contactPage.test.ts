import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const contact = readFileSync(new URL("../app/contact/client.tsx", import.meta.url), "utf8");
const shell = readFileSync(new URL("../components/AppShell.tsx", import.meta.url), "utf8");
const security = readFileSync(new URL("../app/security/client.tsx", import.meta.url), "utf8");
const sitemap = readFileSync(new URL("../app/sitemap.ts", import.meta.url), "utf8");

describe("contact and support surfaces", () => {
  it("links the public contact page from the footer and sitemap", () => {
    expect(shell).toContain('{ href: "/contact", label: "Contact us" }');
    expect(sitemap).toContain("`${base}/contact`");
  });

  it("submits through the server-side contact endpoint", () => {
    expect(contact).toContain('apiPost<{ accepted: boolean }>("/contact"');
    expect(contact).toContain('type="email"');
    expect(contact).toContain("Do not include passwords, payment card details, or API keys.");
  });

  it("does not claim that an unavailable email was sent", () => {
    expect(contact).toContain('state === "error"');
    expect(contact).toContain("We could not send your message");
  });

  it("uses restrained numbering rather than emoji on the security page", () => {
    expect(security).toContain('number: "01"');
    expect(security).toContain('number: "05"');
    expect(security).not.toMatch(/[🔑🗂🤖💳🛡]/u);
  });
});
