// Click-test the measuring tools in the real dashboard (headless Edge). API must be running on :8000.
// Points come from scripts/tools_test_points.json (map positions near target SF17 on the block run).
import { chromium } from "playwright-core";
import { readFileSync } from "node:fs";

const P = JSON.parse(readFileSync(new URL("./tools_test_points.json", import.meta.url)));
const out = "../data/screenshots";
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("dialog", (d) => d.accept("light_utility")); // landing-zones asks which helicopter
await page.goto("http://127.0.0.1:8000/app/", { waitUntil: "networkidle" });
await page.waitForFunction(() => window.__vortex?.mapReady === true, null, { timeout: 30000 });

// frame the area around the clicks, then convert lon/lat -> screen pixels with the map itself
await page.evaluate((p) => window.__vortex.map.fitBounds([p.span[0], p.span[1]], { padding: 260, duration: 0 }), P);
await page.waitForTimeout(1500);
const px = (ll) => page.evaluate(([lng, lat]) => {
  const pt = window.__vortex.map.project([lng, lat]);
  const r = document.getElementById("map").getBoundingClientRect();
  return [r.left + pt.x, r.top + pt.y];
}, ll);
const click = async (ll, n = 1) => { const [x, y] = await px(ll); await page.mouse.click(x, y, { clickCount: n }); await page.waitForTimeout(250); };
const waitResult = async (n) => page.waitForFunction((k) => document.querySelectorAll("#measure-results .item").length >= k, n, { timeout: 120000 });
const results = {};

// 1. span: two clicks, double-click to finish
await page.click('[data-tool="span"]');
await click(P.span[0]);
const [bx, by] = await px(P.span[1]);
await page.mouse.click(bx, by); await page.mouse.dblclick(bx, by);
await waitResult(1);
results.span = await page.locator("#measure-results .item").first().innerText();
results.profile = await page.locator("#profile-body").innerText();
await page.screenshot({ path: `${out}/t1_span.png` });

// 2. volume: four corners, double-click on the last
await page.click('[data-tool="volume"]');
for (const c of P.volume.slice(0, 3)) await click(c);
const [vx, vy] = await px(P.volume[3]);
await page.mouse.click(vx, vy); await page.mouse.dblclick(vx, vy);
await waitResult(2);
results.volume = await page.locator("#measure-results .item").first().innerText();

// 3. working space: one click
await page.click('[data-tool="working-space"]');
await click(P.work);
await waitResult(3);
results.working = await page.locator("#measure-results .item").first().innerText();

// 4. landing zones over the whole map
await page.click('[data-tool="landing-zones"]');
await waitResult(4);
results.landing = await page.locator("#measure-results .item").first().innerText();
await page.screenshot({ path: `${out}/t2_measure_all.png` });

for (const [k, v] of Object.entries(results)) console.log(`--- ${k}\n${v.replace(/\n+/g, " | ").slice(0, 400)}`);
console.log(JSON.stringify({ errors }));
await browser.close();
