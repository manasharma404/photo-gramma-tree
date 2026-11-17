// Headless check of the built app (used when the in-app browser pane is hidden and pauses rendering).
// Usage: node scripts/screenshot.mjs [url] [outdir]   (API must be running on :8000)
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const url = process.argv[2] || "http://127.0.0.1:8000/app/";
const out = process.argv[3] || "../data/screenshots";
mkdirSync(out, { recursive: true });

// Default headless Edge uses the laptop GPU (checked with scripts/webgl_probe.mjs); software WebGL is too slow for 3D.
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
await page.screenshot({ path: `${out}/01_map_act.png` });

for (const tab of ["roads", "accuracy"]) {
  await page.click(`[role=tab][data-tab="${tab}"]`);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${out}/02_${tab}.png` });
}
const first = await page.$("#tab-roads [data-seg]");
await page.click('[role=tab][data-tab="roads"]');
if (first) { await first.click(); await page.waitForTimeout(500); await page.screenshot({ path: `${out}/03_segment.png` }); }

const btn3d = await page.$("#btn-3d:not([disabled])");
if (btn3d) {
  await btn3d.click();
  await page.waitForTimeout(8000);
  await page.screenshot({ path: `${out}/04_3d.png` });
}
const text = await page.evaluate(() => ({
  act: document.getElementById("tab-act").innerText.slice(0, 300),
  roads: document.getElementById("tab-roads").innerText.slice(0, 300),
  accuracy: document.getElementById("tab-accuracy").innerText.slice(0, 300),
  freshness: document.getElementById("freshness").textContent,
  canvases: document.querySelectorAll("canvas").length,
}));
console.log(JSON.stringify({ text, errors: errors.filter((e) => !e.includes("404")) }, null, 2));
await browser.close();
