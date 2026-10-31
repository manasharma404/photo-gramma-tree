// Phone-width screenshot of /field (390 px) for review. Usage: node scripts/field_shot.mjs [base]
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const base = process.argv[2] || "http://localhost:8000";
const out = "../data/screenshots/field";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await page.goto(`${base}/field`, { waitUntil: "networkidle" });
await page.screenshot({ path: `${out}/field_phone_top.png` });
await page.screenshot({ path: `${out}/field_phone_full.png`, fullPage: true });
const wide = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
console.log(JSON.stringify({ title: await page.title(), horizontalScroll: wide, errors }, null, 1));
await browser.close();
