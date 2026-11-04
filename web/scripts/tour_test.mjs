// Walks the dashboard tour (Guide button -> Next ... Done) and screenshots each step.
// Usage: node scripts/tour_test.mjs [base] [width] [height]   ->  ../data/screenshots/tour/
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const base = (process.argv[2] || "http://localhost:8000").replace(/\/$/, "");
const width = Number(process.argv[3] || 1440), height = Number(process.argv[4] || 900);
const out = `../data/screenshots/tour/${width}`;
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await browser.newPage({ viewport: { width, height } });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
await page.goto(`${base}/app/`, { waitUntil: "networkidle" });
await page.waitForSelector(".tour-btn");
await page.click(".tour-btn");
const steps = [];
for (let n = 0; n < 20; n++) {
  await page.waitForTimeout(450);
  const s = await page.evaluate(() => {
    const c = document.querySelector(".tour__card"), sp = document.querySelector(".tour__spot");
    if (!c) return null;
    const r = c.getBoundingClientRect();
    return { count: document.querySelector(".tour__count").textContent, title: document.querySelector("#tour-title").textContent,
      cardInView: r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
      spot: sp.style.display === "none" ? "none" : `${Math.round(parseFloat(sp.style.width))}x${Math.round(parseFloat(sp.style.height))}` };
  });
  if (!s) break;
  steps.push(s);
  await page.screenshot({ path: `${out}/step_${String(n + 1).padStart(2, "0")}.png` });
  await page.click(".tour__next");
}
const gone = await page.evaluate(() => !document.querySelector(".tour"));
console.log(JSON.stringify({ steps, closedAtEnd: gone, errors }, null, 1));
await browser.close();
