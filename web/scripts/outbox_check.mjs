// Field outbox check in a real browser (item 4): sign in with a team PIN, go offline, send a report (kept on the
// phone), come back online (it sends itself), then save the map PDF. The test report is marked "TEST outbox" so it
// can be removed afterwards. Codes are read from .env, never printed.
// Usage: CDP=http://127.0.0.1:9222 node scripts/outbox_check.mjs [outdir]
import { chromium } from "playwright-core";
import { mkdirSync, readFileSync } from "node:fs";

const out = process.argv[2] || "outbox_check";
mkdirSync(out, { recursive: true });
const env = Object.fromEntries(readFileSync(new URL("../../.env", import.meta.url), "utf8").split(/\r?\n/)
  .filter((l) => l.includes("=") && !l.startsWith("#")).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]));
const pin = env.VORTEX_TEAM_PINS.split(",")[0].split(":").pop();
const base = "http://127.0.0.1:8000";
const browser = process.env.CDP ? await chromium.connectOverCDP(process.env.CDP) : await chromium.launch({ channel: "msedge" });
const ctx = await browser.newContext({ viewport: { width: 400, height: 860 }, acceptDownloads: true });
const page = await ctx.newPage();
const res = {};
await page.goto(`${base}/login/`);
await page.fill("#code", pin);
await page.click("#go");
await page.waitForURL(/\/field/);
await page.waitForFunction(() => /Selected ->/.test(document.body.innerText), null, { timeout: 20000 });
res.selected = (await page.innerText("body")).match(/Selected ->[^\n]*/)[0];

await ctx.setOffline(true);
await page.fill("#report-callsign", "TEST outbox");
await page.waitForSelector("#submit-btn:not([disabled])", { timeout: 10000 });
await page.click("#submit-btn");
await page.waitForSelector(".outbox:not([hidden])", { timeout: 10000 });
res.toast_offline = await page.textContent("#toast");
res.outbox_offline = await page.textContent(".outbox b");
await page.screenshot({ path: `${out}/1_offline_kept.png`, fullPage: false });

await ctx.setOffline(false);
await page.waitForSelector(".outbox[hidden]", { state: "attached", timeout: 30000 });
res.outbox_after_reconnect = await page.textContent(".outbox__msg");
const reports = await page.evaluate(() => fetch("/advisor/reports").then((r) => r.json()));
const mine = (reports.reports || []).filter((r) => /TEST outbox/.test(r.reporter || "") || /phone outbox/.test(r.note || ""));
res.arrived_on_laptop = mine.map((r) => ({ reporter: r.reporter, note: r.note, segment: r.segment_id }));

const t0 = Date.now();
const [dl] = await Promise.all([page.waitForEvent("download", { timeout: 120000 }), page.click(".outbox__save")]);
const path = `${out}/saved_map.pdf`;
await dl.saveAs(path);
res.saved_map = { file: dl.suggestedFilename(), seconds: Math.round((Date.now() - t0) / 1000),
                  starts_with_pdf: readFileSync(path).subarray(0, 5).toString() === "%PDF-" };
console.log(JSON.stringify(res, null, 1));
await ctx.close();
await browser.close();
