// Field PIN, end to end as a phone sees it: a report without the PIN is refused, the same report with it is saved.
// Usage: FIELD_PIN=<pin the server printed> node scripts/field_pin_test.mjs http://<laptop-ip>:8000
// Use the laptop's network address, not 127.0.0.1: the laptop itself is trusted and never asked for the PIN.
// Run the API with a throwaway database (VORTEX_ADVISOR_DB=...) so the test report never reaches real data.
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const base = (process.argv[2] || "").replace(/\/$/, "");
const pin = process.env.FIELD_PIN || "";
if (!base || /127\.0\.0\.1|localhost/.test(base) || !pin) {
  console.error("needs FIELD_PIN and the laptop's network address, e.g. http://10.0.0.5:8000");
  process.exit(2);
}
const out = "../data/screenshots/field_pin";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(`${base}/field`, { waitUntil: "networkidle" });
await page.locator(".loc-item").last().click();
await page.locator('[data-kind="dead_end"]').click();
await page.fill("#report-callsign", "field_pin_test");

const send = async () => {
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith("/advisor/reports") && r.request().method() === "POST"),
    page.click("#submit-btn"),
  ]);
  await page.waitForTimeout(600);
  return { status: resp.status(), toast: (await page.locator("#toast").innerText()).trim() };
};

const without = await send();
await page.locator("#report-pin").scrollIntoViewIfNeeded();
await page.screenshot({ path: `${out}/1_refused.png` });
await page.fill("#report-pin", pin);
const withPin = await send();
await page.screenshot({ path: `${out}/2_saved.png` });
await browser.close();

const ok = without.status === 403 && /PIN/.test(without.toast) && withPin.status === 200 && /Saved report/.test(withPin.toast)
  && errors.length === 0;
console.log(JSON.stringify({ ok, without, with_pin: { status: withPin.status, toast: withPin.toast }, errors }, null, 1));
process.exit(ok ? 0 : 1);
