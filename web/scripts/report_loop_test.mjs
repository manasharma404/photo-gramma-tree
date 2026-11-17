// Field report loop, end to end: the dashboard is open, a phone sends a report, the dashboard recolours the road,
// recounts cut-off places and shows a notice, without a reload.
// Usage: node scripts/report_loop_test.mjs [base]
// Run the API with a throwaway database (VORTEX_ADVISOR_DB=...) so the test report never reaches real data.
import { chromium } from "playwright-core";
import { mkdirSync } from "node:fs";

const base = (process.argv[2] || "http://127.0.0.1:8000").replace(/\/$/, "");
const out = "../data/screenshots/report_loop";
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

await page.goto(`${base}/app/`, { waitUntil: "networkidle" });
await page.waitForFunction(() => window.__vortex?.mapReady === true, null, { timeout: 60000 });
const project = (await (await fetch(`${base}/accuracy/active`)).json()).project;
const ctx = await (await fetch(`${base}/advisor/context?project=${project}`)).json();
// the last listed place: on South Fork the first is the staging base (the campground)
const place = ctx.places.filter((p) => p.nearest_segment_id).at(-1);
const cutBefore = await page.locator("#tab-act").innerText();
await page.screenshot({ path: `${out}/1_before.png` });

// the phone's report, sent exactly as /field sends it
const res = await fetch(`${base}/advisor/reports`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ project, kind: "dead_end", place_id: place.place_id, note: "test: slide across the trail", reporter: "report_loop_test" }),
});
const posted = await res.json();
const seg = posted.report?.segment_id;

await page.waitForSelector("#report-toast.is-on", { timeout: 15000 });
await page.waitForTimeout(1600);
await page.screenshot({ path: `${out}/2_after.png` });
const toast = (await page.locator("#report-toast").innerText()).replace(/\s+/g, " ");
const status = await page.evaluate((id) => window.__vortex?.map?.querySourceFeatures?.("segments")
  .find((f) => f.properties.segment_id === id)?.properties.status, seg);
const cutAfter = await page.locator("#tab-act").innerText();
const pick = (t) => t.match(/Places cut off[^\n]*\n?\s*([^\n]+)/)?.[1]?.trim();
await browser.close();

const ok = res.ok && !!toast && status === "blocked" && errors.length === 0;
console.log(JSON.stringify({ ok, project, place: place.place_id, segment: seg, status, toast,
  cut_before: pick(cutBefore), cut_after: pick(cutAfter), errors }, null, 1));
process.exit(ok ? 0 : 1);
