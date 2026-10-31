// Capture a stand-in hero image from our real 3D terrain (USGS public data) for the landing page.
// Usage: node scripts/hero_render.mjs  (API on :8000; writes public/hero-standin.png)
import { chromium } from "playwright-core";

const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1800, height: 1100 }, deviceScaleFactor: 1 });
await page.goto("http://127.0.0.1:8000/app/", { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
await page.click("#btn-3d");
await page.waitForTimeout(8000);
// hide all UI so only the terrain on sand remains
await page.addStyleTag({ content: ".topbar,.rail,.panel,.strip,.viewswitch,.legend,.hint,.layers,.toolcol,.fab{display:none!important} body.app{grid-template-rows:0 1fr 0!important} .workspace{grid-template-columns:1fr!important}" });
await page.waitForTimeout(3000);
await page.screenshot({ path: "public/hero-standin.png" });
await browser.close();
console.log("wrote public/hero-standin.png");
