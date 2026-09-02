/**
 * Per-route client cost, measured from the browser rather than the build.
 *
 * Next 16's App Router does not print per-route bundle sizes, and its build
 * manifests do not map routes to client chunks in a form that survives a
 * version bump. What a visitor actually downloads is the number that matters,
 * so this asks a real page load what it fetched.
 *
 * Usage: node scripts/measure-routes.mjs [baseUrl]
 * Requires the production server to be running (npm run build && npm run start).
 */

const BASE = process.argv[2] ?? "http://localhost:3001";
const ROUTES = ["/", "/discover", "/world", "/pricing", "/login", "/security"];

/**
 * Resources are collected after the load event plus a settle delay: lazily
 * imported chunks (both globes, and anything else behind next/dynamic) arrive
 * after load, and omitting them would report a flattering number that no
 * visitor experiences.
 */
const SETTLE_MS = 3000;

const kb = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;

async function main() {
  let puppeteer;
  try {
    puppeteer = await import("puppeteer");
  } catch {
    console.error(
      "puppeteer is not installed. This script is a measuring tool, not part of\n" +
        "the build — install it only when you need a reading:\n" +
        "  npm i -D puppeteer\n",
    );
    process.exit(1);
  }

  const browser = await puppeteer.launch();
  const rows = [];

  for (const route of ROUTES) {
    const page = await browser.newPage();
    await page.goto(BASE + route, { waitUntil: "load", timeout: 60000 });
    await new Promise((r) => setTimeout(r, SETTLE_MS));

    const stats = await page.evaluate(() => {
      const resources = performance.getEntriesByType("resource");
      const sum = (predicate) =>
        resources
          .filter(predicate)
          .reduce((total, r) => total + (r.transferSize || 0), 0);
      const isJs = (r) => /\.js(\?|$)/.test(r.name);
      const isFont = (r) => /\.(woff2?|ttf|otf)(\?|$)/.test(r.name);
      const isCss = (r) => /\.css(\?|$)/.test(r.name);
      return {
        js: sum(isJs),
        jsCount: resources.filter(isJs).length,
        font: sum(isFont),
        fontCount: resources.filter(isFont).length,
        css: sum(isCss),
        html: performance.getEntriesByType("navigation")[0]?.transferSize ?? 0,
      };
    });

    rows.push({ route, ...stats });
    await page.close();
  }

  await browser.close();

  console.log(
    "\n| Route | JS (files) | Fonts (files) | CSS | HTML | Total |",
  );
  console.log("|---|---|---|---|---|---|");
  for (const r of rows) {
    const total = r.js + r.font + r.css + r.html;
    console.log(
      `| \`${r.route}\` | ${kb(r.js)} (${r.jsCount}) | ${kb(r.font)} (${r.fontCount}) | ${kb(r.css)} | ${kb(r.html)} | **${kb(total)}** |`,
    );
  }
  console.log("");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
