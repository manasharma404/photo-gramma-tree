// Screenshots of the home hero at common laptop sizes, plus overlap checks between hero parts.
// Usage: node scripts/hero_sizes.mjs [base]   ->  ../data/screenshots/hero/<w>x<h>.png
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const base = (process.argv[2] || "http://localhost:8000").replace(/\/$/, "");
const out = "../data/screenshots/hero";
mkdirSync(out, { recursive: true });
const sizes = [[1280, 680], [1366, 768], [1440, 900], [1536, 864], [1920, 1080], [1024, 700]];
const browser = await chromium.launch({ channel: "msedge", headless: true });
const report = {};
for (const [w, h] of sizes) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.goto(`${base}/`, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: `${out}/${w}x${h}.png` });
  report[`${w}x${h}`] = await page.evaluate(() => {
    const sel = [".lnav .brand", ".lnav__links", ".pill-cta", ".col--left .tag", ".col--left .coords", ".features", ".tagline",
      ".col--right .view3d", ".layers-list", ".compass", ".col--right .coords", ".corner--left", ".corner--right", ".explore"];
    const boxes = sel.map((s) => [s, document.querySelector(s)]).filter(([, e]) => e && e.getClientRects().length && getComputedStyle(e).display !== "none")
      .map(([s, e]) => [s, e.getBoundingClientRect()]);
    const hit = [];
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const [a, ra] = boxes[i], [b, rb] = boxes[j];
      if (ra.left < rb.right && rb.left < ra.right && ra.top < rb.bottom && rb.top < ra.bottom) hit.push(`${a} × ${b}`);
    }
    const links = document.querySelector(".lnav__links").getBoundingClientRect();
    return { overlaps: hit, navLinksCentreOffset: Math.round(links.left + links.width / 2 - innerWidth / 2) };
  });
  await page.close();
}
await browser.close();
console.log(JSON.stringify(report, null, 1));
