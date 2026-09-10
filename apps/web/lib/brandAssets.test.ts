import { existsSync, readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const appShell = readFileSync(new URL("../components/AppShell.tsx", import.meta.url), "utf8");
const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
const manifest = readFileSync(new URL("../app/manifest.ts", import.meta.url), "utf8");
const mark = readFileSync(new URL("../public/farelin-icon.svg", import.meta.url), "utf8");
const faviconUrl = new URL("../public/farelin-app-icon-7f83cc1f.png", import.meta.url);

describe("Farelin brand assets", () => {
  it("uses the exported Farelin Icon in the shared navigation and footer", () => {
    expect(appShell).toContain('src="/farelin-icon.svg"');
    expect(appShell).toContain("<FarelinMark />");
    expect(appShell).toContain("<FarelinMark size={20} />");
    expect(appShell).not.toContain("M7 20c4-8 14-11 18-8");
    expect(mark).toContain('id="Farelin Icon"');
    expect(mark).toContain("linearGradient");
  });

  it("uses the complete square Frame app export as the favicon", () => {
    expect(existsSync(faviconUrl)).toBe(true);
    const png = readFileSync(faviconUrl);
    expect(png.subarray(1, 4).toString()).toBe("PNG");
    expect(png.readUInt32BE(16)).toBe(1000);
    expect(png.readUInt32BE(20)).toBe(1000);
    expect(layout).toContain('url: "/farelin-app-icon-7f83cc1f.png"');
    expect(layout).toContain('shortcut: ["/farelin-app-icon-7f83cc1f.png"]');
    expect(layout).toContain("apple:");
    expect(manifest).toContain('src: "/farelin-app-icon-7f83cc1f.png"');
  });
});
