// Projector-size screenshots for the deck (16:9, 2x pixels). API must be running on :8000.
// Usage: node scripts/deck_shots.mjs [outdir]
import { chromium } from "playwright-core";
import { mkdirSync, readFileSync } from "node:fs";

const out = process.argv[2] || "../data/screenshots/deck";
mkdirSync(out, { recursive: true });
const P = JSON.parse(readFileSync(new URL("./tools_test_points.json", import.meta.url)));
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 2 });
const errors = [];
const page = await ctx.newPage();
page.on("pageerror", (e) => errors.push(String(e)));
const shot = (name) => page.screenshot({ path: `${out}/${name}.png` });

// landing page
await page.goto("http://127.0.0.1:8000/", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await shot("01_landing");

// dashboard, Act now
await page.goto("http://127.0.0.1:8000/app/", { waitUntil: "networkidle" });
await page.waitForFunction(() => window.__vortex?.mapReady === true, null, { timeout: 30000 });
await page.waitForTimeout(2500);
await shot("02_dashboard_act");

// accuracy: framed on the checkpoint arrows
await page.click('[role=tab][data-tab="accuracy"]');
await page.evaluate(async () => {
  const fc = await (await fetch("/accuracy/layers/checkpoints")).json();
  const xs = [], ys = [];
  for (const f of fc.features) for (const [x, y] of f.geometry.coordinates) { xs.push(x); ys.push(y); }
  window.__vortex.map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], { padding: 160, duration: 0 });
});
await page.waitForTimeout(2500);
await shot("03_accuracy_arrows");

// roads: first segment selected
await page.click('[role=tab][data-tab="roads"]');
const seg = await page.$("#tab-roads [data-seg]");
if (seg) { await seg.click(); await page.waitForTimeout(1500); }
await shot("04_roads_segment");

// span measurement with its cross-section
await page.evaluate((p) => window.__vortex.map.fitBounds([p.span[0], p.span[1]], { padding: 300, duration: 0 }), P);
await page.waitForTimeout(1500);
const px = (ll) => page.evaluate(([lng, lat]) => {
  const pt = window.__vortex.map.project([lng, lat]);
  const r = document.getElementById("map").getBoundingClientRect();
  return [r.left + pt.x, r.top + pt.y];
}, ll);
await page.click('[data-tool="span"]');
const [ax, ay] = await px(P.span[0]);
await page.mouse.click(ax, ay); await page.waitForTimeout(250);
const [bx, by] = await px(P.span[1]);
await page.mouse.click(bx, by); await page.mouse.dblclick(bx, by);
await page.waitForFunction(() => document.querySelectorAll("#measure-results .item").length >= 1, null, { timeout: 120000 });
await page.waitForTimeout(1000);
await shot("05_span_measure");

// 3D view
const btn3d = await page.$("#btn-3d:not([disabled])");
if (btn3d) { await btn3d.click(); await page.waitForTimeout(9000); await shot("06_3d"); }

console.log(JSON.stringify({ out, errors }));
await browser.close();
