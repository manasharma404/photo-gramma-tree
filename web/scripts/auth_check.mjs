// Sign-in check in a real browser: the map needs a code; a wrong code is refused; the judges' code opens the map;
// a team PIN opens the phone report page and nothing else. Codes are read from the laptop's .env, never printed.
// Usage: CDP=http://127.0.0.1:9222 node scripts/auth_check.mjs [outdir]   (API on :8000 with sign-in on)
import { chromium } from "playwright-core";
import { mkdirSync, readFileSync } from "node:fs";

const out = process.argv[2] || "auth_check";
mkdirSync(out, { recursive: true });
const env = Object.fromEntries(readFileSync(new URL("../../.env", import.meta.url), "utf8").split(/\r?\n/)
  .filter((l) => l.includes("=") && !l.startsWith("#")).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]));
const teamPin = env.VORTEX_TEAM_PINS.split(",")[0].split(":").pop();
const base = "http://127.0.0.1:8000";
const browser = process.env.CDP ? await chromium.connectOverCDP(process.env.CDP) : await chromium.launch({ channel: "msedge" });
const results = {};

async function fresh() {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  return [ctx, await ctx.newPage()];
}

// 1. not signed in: the map sends you to sign in
let [ctx, page] = await fresh();
await page.goto(`${base}/app/`);
results.redirected_to = new URL(page.url()).pathname + new URL(page.url()).search;
await page.screenshot({ path: `${out}/1_sign_in_page.png` });
// 2. a wrong code is refused with a message
await page.fill("#code", "not-the-code");
await page.click("#go");
await page.waitForFunction(() => document.getElementById("msg").textContent.length > 0);
results.wrong_code_message = await page.textContent("#msg");
// 3. the judges' code opens the map, and the top bar says who is signed in
await page.fill("#code", env.VORTEX_EVALUATOR_CODE);
await page.click("#go");
await page.waitForURL(/\/app\//);
await page.waitForSelector("#who:not([hidden])", { timeout: 15000 });
results.evaluator_landed_on = new URL(page.url()).pathname;
results.evaluator_badge = await page.textContent("#who");
const skip = page.getByRole("button", { name: /skip tour/i });
if (await skip.isVisible({ timeout: 4000 }).catch(() => false)) await skip.click();
await page.waitForTimeout(1500);
await page.screenshot({ path: `${out}/2_evaluator_map.png` });
await ctx.close();
// 4. a team PIN opens only the report page
[ctx, page] = await fresh();
await page.goto(`${base}/login/`);
await page.fill("#code", teamPin);
await page.click("#go");
await page.waitForURL(/\/field/);
results.team_landed_on = new URL(page.url()).pathname;
await page.goto(`${base}/app/`);
results.team_opening_map_lands_on = new URL(page.url()).pathname;
results.team_live_api_status = await page.evaluate(() => fetch("/live/sets").then((r) => r.status));
await page.waitForLoadState("networkidle");
await page.waitForFunction(() => !/loading/i.test(document.body.innerText.split("\n").slice(0, 6).join(" ")), null, { timeout: 15000 })
  .catch(() => {});
results.team_page_scenarios = await page.$$eval("select option", (os) => os.map((o) => o.textContent.trim()));
await page.screenshot({ path: `${out}/3_team_field_page.png` });
await ctx.close();
console.log(JSON.stringify(results, null, 1));
await browser.close();
