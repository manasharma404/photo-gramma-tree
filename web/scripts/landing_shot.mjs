// Headless check of the landing page at laptop and phone size. API must be running on :8000.
import { chromium } from "playwright-core";

const out = process.argv[2] || "../data/screenshots";
const browser = await chromium.launch({ channel: "msedge", headless: true });
const errors = [];
for (const [name, vp, mobile] of [["l1_landing", { width: 1440, height: 900 }, false], ["l2_landing_phone", { width: 390, height: 844 }, true]]) {
  const page = await browser.newPage({ viewport: vp, isMobile: mobile, deviceScaleFactor: mobile ? 2 : 1 });
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${out}/${name}.png` });
  if (!mobile) await page.screenshot({ path: `${out}/l3_landing_full.png`, fullPage: true });
  await page.close();
}
console.log(JSON.stringify({ errors }));
await browser.close();
