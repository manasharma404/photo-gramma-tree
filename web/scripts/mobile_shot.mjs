// Headless phone-size check of the dashboard (390 x 844, touch). API must be running on :8000.
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const url = process.argv[2] || "http://127.0.0.1:8000/app/";
const out = process.argv[3] || "../data/screenshots";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
await page.screenshot({ path: `${out}/m1_map.png` });
await page.tap("#panel-head");
await page.waitForTimeout(600);
await page.screenshot({ path: `${out}/m2_sheet.png` });
await page.tap("#panel-head");
await page.tap("#layers-btn");
await page.waitForTimeout(400);
await page.screenshot({ path: `${out}/m3_layers.png` });
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
console.log(JSON.stringify({ horizontalOverflow: overflow, errors }));
await browser.close();
