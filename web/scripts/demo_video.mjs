// Records a ~2 minute walkthrough of the real laptop app (headless Edge), with short captions on screen.
// Usage: node scripts/demo_video.mjs [base]   ->  ../data/screenshots/demo/*.webm (convert with ffmpeg)
// API must be running on :8000. Every caption describes what is on screen; numbers come from the app itself.
import { chromium } from "playwright-core";
import { readFileSync, mkdirSync, writeFileSync, rmSync } from "node:fs";

const base = (process.argv[2] || "http://127.0.0.1:8000").replace(/\/$/, "");
const P = JSON.parse(readFileSync(new URL("./tools_test_points.json", import.meta.url)));
const out = "../data/screenshots/demo";
mkdirSync(out, { recursive: true });
const size = { width: 1440, height: 900 };
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const ctx = await browser.newContext({ viewport: size });
const page = await ctx.newPage();
// frames come from the browser's own screencast feed (no extra download); ffmpeg on the laptop joins them
const frames = `${out}/frames`;
rmSync(frames, { recursive: true, force: true });
mkdirSync(frames, { recursive: true });
const cdp = await ctx.newCDPSession(page);
const shots = [];
cdp.on("Page.screencastFrame", async ({ data, metadata, sessionId }) => {
  const f = `${frames}/${String(shots.length).padStart(5, "0")}.jpg`;
  writeFileSync(f, Buffer.from(data, "base64"));
  shots.push([f, metadata.timestamp]);
  await cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
});
const startCast = () => cdp.send("Page.startScreencast", { format: "jpeg", quality: 85, maxWidth: size.width, maxHeight: size.height });
await startCast();
page.on("load", () => startCast().catch(() => {}));
page.on("dialog", (d) => d.accept("light_utility"));
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
const wait = (ms) => page.waitForTimeout(ms);

// caption bar, added to every page for the recording only
const caption = async (text) => page.evaluate((t) => {
  let el = document.getElementById("demo-caption");
  if (!el) {
    el = document.createElement("div");
    el.id = "demo-caption";
    el.style.cssText = "position:fixed;left:50%;bottom:28px;transform:translateX(-50%);z-index:99999;max-width:900px;" +
      "padding:12px 22px;border-radius:999px;background:rgba(15,30,61,.92);color:#F5F1E6;font:500 17px 'Space Grotesk',Inter,sans-serif;" +
      "letter-spacing:.01em;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,.25);transition:opacity .3s";
    document.body.append(el);
  }
  el.style.opacity = t ? "1" : "0";
  if (t) el.textContent = t;
}, text);
const smoothScroll = async (to, ms) => {
  await page.evaluate(([y, d]) => new Promise((res) => {
    const y0 = scrollY, t0 = performance.now();
    const step = (t) => { const k = Math.min(1, (t - t0) / d); const e = k < .5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;
      scrollTo(0, y0 + (y - y0) * e); k < 1 ? requestAnimationFrame(step) : res(); };
    requestAnimationFrame(step);
  }), [to, ms]);
};
const yOf = (sel) => page.evaluate((s) => document.querySelector(s).getBoundingClientRect().top + scrollY - 80, sel);

// 1. home
await page.goto(`${base}/`, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await caption("Project Typhon: drone footage to a road map, on one laptop, with no internet");
await wait(4000);
await caption("About: the problem, how it works, and the numbers from our runs");
await smoothScroll(await yOf("#about"), 3500); await wait(1500);
await smoothScroll(await yOf("#about") + 1500, 4000); await wait(2500);
await caption("Drone data: our own DJI Neo 2 flight, and what it taught us");
await smoothScroll(await yOf("#drone-data"), 4000); await wait(3000);

// 2. dashboard
await page.goto(`${base}/app/`, { waitUntil: "networkidle" });
await page.waitForFunction(() => window.__vortex?.mapReady === true, null, { timeout: 60000 });
await caption("The dashboard: USGS public survey photos of a real debris flow, mapped without ground control");
await wait(4000);
await page.click(".tour-btn");
await caption("A guided tour explains each part for a first-time user");
for (let i = 0; i < 4; i++) { await wait(2600); await page.click(".tour__next"); }
await wait(2400);
await page.keyboard.press("Escape");
await caption("Pick who is going: every road and count updates for that vehicle");
for (const v of ["fire_truck", "ambulance", "foot"]) { await page.click(`#vehicle [data-v="${v}"]`); await wait(1500); }
await caption("Roads under tree canopy stay “unknown”: never shown as open");
await wait(3500);

// 3. measure a span across the debris channel
await page.click('[data-tab="measure"]');
await page.evaluate((p) => window.__vortex.map.fitBounds([p.span[0], p.span[1]], { padding: 260, duration: 1200 }), P);
await wait(2000);
const px = (ll) => page.evaluate(([lng, lat]) => {
  const pt = window.__vortex.map.project([lng, lat]);
  const r = document.getElementById("map").getBoundingClientRect();
  return [r.left + pt.x, r.top + pt.y];
}, ll);
await caption("Measure: draw a span across the debris channel");
await page.click('[data-tool="span"]');
const [ax, ay] = await px(P.span[0]); await page.mouse.move(ax, ay, { steps: 12 }); await page.mouse.click(ax, ay); await wait(600);
const [bx, by] = await px(P.span[1]); await page.mouse.move(bx, by, { steps: 25 }); await page.mouse.click(bx, by); await page.mouse.dblclick(bx, by);
await page.waitForFunction(() => document.querySelectorAll("#measure-results .item").length >= 1, null, { timeout: 120000 });
const spanText = (await page.locator("#measure-results .item").first().innerText()).replace(/\s+/g, " ");
const span = spanText.match(/Span\s+([\d.]+ m ± [\d.]+ m)/)?.[1];
await caption(span ? `Span ${span}: every result carries its tolerance, plus a height profile` : "Every result carries its tolerance, plus a height profile");
await wait(5000);

// 4. accuracy and 3D
await page.click('[data-tab="accuracy"]');
await caption("Accuracy: how far off the map is, measured against surveyed checkpoints");
await wait(5000);
await page.click("#btn-3d");
await caption("3D terrain from the same photos");
await wait(6000);

// 5. field page
await page.goto(`${base}/field`, { waitUntil: "networkidle" });
await page.selectOption("#project-select", "southfork_f01_4").catch(() => {});
await wait(1200);
await caption("Field teams report from a phone on the laptop's hotspot; reports update road status");
await wait(5000);
await caption("Read-only copy: manasharma404.github.io/photo-gramma-tree · code on GitHub");
await wait(4000);

await cdp.send("Page.stopScreencast").catch(() => {});
await ctx.close();
await browser.close();
// ffmpeg concat list: each frame shown until the next one arrived
const list = shots.map(([f, t], i) => {
  const d = i + 1 < shots.length ? Math.max(0.001, shots[i + 1][1] - t) : 1;
  return `file '${f.split("/").pop()}'\nduration ${d.toFixed(3)}`;
}).join("\n");
writeFileSync(`${frames}/list.txt`, list + `\nfile '${shots.at(-1)[0].split("/").pop()}'\n`);
console.log(JSON.stringify({ frames: shots.length, seconds: +(shots.at(-1)[1] - shots[0][1]).toFixed(1), span, errors }));
