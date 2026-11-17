// Offline check: load every page and view, list any request that leaves this laptop.
// The brief says no internet at runtime; this proves it for the UI before the phone test.
// Usage: node scripts/offline_check.mjs [base]   (API must be running on :8000)
import { chromium } from "playwright-core";

const base = (process.argv[2] || "http://127.0.0.1:8000").replace(/\/$/, "");
const local = (u) => /^(data:|blob:)/.test(u) || new URL(u).origin === new URL(base).origin;

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true });
const outside = new Set(), failed = [], errors = [];
let requests = 0;

for (const [path, viewport] of [["/", { width: 1440, height: 900 }], ["/app/", { width: 1440, height: 900 }],
                                ["/app/", { width: 390, height: 844 }], ["/field", { width: 390, height: 844 }]]) {
  const page = await browser.newPage({ viewport });
  page.on("request", (r) => { requests++; if (!local(r.url())) outside.add(r.url()); });
  page.on("requestfailed", (r) => failed.push(`${path} ${r.url()} ${r.failure()?.errorText}`));
  page.on("response", (r) => r.status() >= 400 && failed.push(`${path} ${r.url()} HTTP ${r.status()}`));
  page.on("pageerror", (e) => errors.push(`${path} ${e}`));
  await page.goto(base + path, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  if (path === "/app/" && viewport.width > 800) {
    for (const tab of ["roads", "accuracy", "act"]) {
      await page.click(`[role=tab][data-tab="${tab}"]`);
      await page.waitForTimeout(400);
    }
    const btn3d = await page.$("#btn-3d:not([disabled])");
    if (btn3d) { await btn3d.click(); await page.waitForTimeout(5000); }
  }
  await page.close();
}
await browser.close();
console.log(JSON.stringify({ requests, outside: [...outside], failed, errors }, null, 2));
process.exit(outside.size || errors.length ? 1 : 0);
