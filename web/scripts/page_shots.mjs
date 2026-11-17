// Full-page screenshots of the content pages at desktop and phone width, plus checks:
// broken images, horizontal scroll, failed requests, console errors.
// Usage: node scripts/page_shots.mjs [base]   ->  ../data/screenshots/pages/
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const base = (process.argv[2] || "http://localhost:8000").replace(/\/$/, "");
const out = "../data/screenshots/pages";
mkdirSync(out, { recursive: true });
const pages = [["home", "/"], ["app", "/app/"]];
const sizes = [["desktop", { width: 1440, height: 900 }], ["phone", { width: 390, height: 844 }]];

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true });
const report = [];
for (const [sname, viewport] of sizes) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  for (const [name, path] of pages) {
    const errors = [], failed = [];
    const onErr = (e) => errors.push(e.message || e.text());
    page.on("pageerror", onErr);
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("requestfailed", (r) => failed.push(r.url()));
    page.on("response", (r) => r.status() >= 400 && failed.push(`${r.status()} ${r.url()}`));
    await page.goto(base + path, { waitUntil: "networkidle" });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(400);
    const info = await page.evaluate(() => ({
      brokenImages: [...document.images].filter((i) => !i.complete || i.naturalWidth === 0).map((i) => i.getAttribute("src")),
      horizontalScroll: document.documentElement.scrollWidth > window.innerWidth + 1,
      fonts: [...document.fonts].filter((f) => f.status === "loaded").map((f) => `${f.family} ${f.weight} ${f.style}`),
      facts: [...document.querySelectorAll("[data-fact]")].map((e) => e.textContent),
    }));
    await page.screenshot({ path: `${out}/${name}_${sname}.png`, fullPage: true });
    report.push({ page: name, size: sname, ...info, errors, failed });
    page.removeAllListeners();
  }
  await page.close();
}
await browser.close();
console.log(JSON.stringify(report, null, 1));
