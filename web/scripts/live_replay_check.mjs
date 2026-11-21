// Growing-map check (F1), end to end in a real browser: open the app, start a real-time replay of a photo set,
// screenshot it mid-flight and at the end, and print the server's own numbers (kept pace? how many waiting?).
// Usage: node scripts/live_replay_check.mjs [set] [outdir]   (API running on :8000)
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const set = process.argv[2] || "southfork_block";
const out = process.argv[3] || "live_check";
mkdirSync(out, { recursive: true });
const base = "http://127.0.0.1:8000";
// Playwright could not launch this machine's Edge directly any more (21 Nov), so the browser may be started by hand
// with a debugging port and joined here:  msedge --headless=new --remote-debugging-port=9222 --user-data-dir=<tmp>
const browser = process.env.CDP
  ? await chromium.connectOverCDP(process.env.CDP)
  : await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true });
const context = browser.contexts()[0] || (await browser.newContext());
const page = await context.newPage();
await page.setViewportSize({ width: 1440, height: 900 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.goto(`${base}/app/`);
const skip = page.getByRole("button", { name: /skip tour/i });
if (await skip.isVisible({ timeout: 8000 }).catch(() => false)) await skip.click();
await page.waitForSelector("#live-set option[value]", { state: "attached", timeout: 30000 });
await page.selectOption("#live-set", set);
await page.click("#live-go");
const t0 = Date.now();
const samples = [];
let st;
for (;;) {
  await page.waitForTimeout(10000);
  st = await (await fetch(`${base}/live/status`)).json();
  samples.push({ t: Math.round((Date.now() - t0) / 1000), placed: st.placed, due: st.arrived, behind: st.behind,
                 lag: st.arrival_to_placed_s_recent, work: st.work_s_per_photo_recent });
  console.log(JSON.stringify(samples.at(-1)));
  if (samples.length === 6) await page.screenshot({ path: `${out}/mid_flight.png` });
  if (!["running", "finishing"].includes(st.state)) break;
}
await page.waitForTimeout(2500);
await page.screenshot({ path: `${out}/end.png` });
const layers = await page.evaluate(() => window.__vortex.map.getStyle().layers.filter((l) => l.id.startsWith("live-")).length);
const card = await page.locator("#live").innerText();
console.log(JSON.stringify({ final: st, photo_layers_on_map: layers, card, page_errors: errors }, null, 1));
await browser.close();
