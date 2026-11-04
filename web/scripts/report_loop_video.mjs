// Records the field report loop as two clips for the demo video: a phone sending a report on /field, and the
// dashboard reacting (road turns red, cut-off count updates, notice). Same screencast method as demo_video.mjs.
// Usage: node scripts/report_loop_video.mjs [base]   ->  ../data/screenshots/report_loop/{phone,dash}/ + list.txt
// Run the API with a throwaway database (VORTEX_ADVISOR_DB=...) so the recorded report never reaches real data.
import { chromium } from "playwright-core";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";

const base = (process.argv[2] || "http://127.0.0.1:8000").replace(/\/$/, "");
const out = "../data/screenshots/report_loop";
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] });

async function recorded(name, options) {
  const ctx = await browser.newContext(options);
  const page = await ctx.newPage();
  const dir = `${out}/${name}`;
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const cdp = await ctx.newCDPSession(page);
  const shots = [];
  cdp.on("Page.screencastFrame", async ({ data, metadata, sessionId }) => {
    const f = `${dir}/${String(shots.length).padStart(5, "0")}.jpg`;
    writeFileSync(f, Buffer.from(data, "base64"));
    shots.push([f, metadata.timestamp]);
    await cdp.send("Page.screencastFrameAck", { sessionId }).catch(() => {});
  });
  const vp = options.viewport;
  const start = () => cdp.send("Page.startScreencast", { format: "jpeg", quality: 90, maxWidth: vp.width * 2, maxHeight: vp.height * 2 });
  page.on("load", () => start().catch(() => {}));
  await start();
  const finish = async () => {
    await cdp.send("Page.stopScreencast").catch(() => {});
    const list = shots.map(([f, t], i) => `file '${f.split("/").pop()}'\nduration ${(i + 1 < shots.length ? Math.max(0.001, shots[i + 1][1] - t) : 1).toFixed(3)}`);
    writeFileSync(`${dir}/list.txt`, list.join("\n") + `\nfile '${shots.at(-1)[0].split("/").pop()}'\n`);
    return { frames: shots.length, seconds: +(shots.at(-1)[1] - shots[0][1]).toFixed(1) };
  };
  return { page, finish };
}

const dash = await recorded("dash", { viewport: { width: 1440, height: 900 } });
const phone = await recorded("phone", { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
const errors = [];
for (const p of [dash.page, phone.page]) p.on("pageerror", (e) => errors.push(String(e)));

await dash.page.goto(`${base}/app/`, { waitUntil: "networkidle" });
await dash.page.waitForFunction(() => window.__vortex?.mapReady === true, null, { timeout: 60000 });
await phone.page.goto(`${base}/field`, { waitUntil: "networkidle" });
await phone.page.waitForSelector(".loc-item");
await phone.page.waitForTimeout(1500);

// the responder picks the place, keeps "dead end", signs and sends
await phone.page.locator(".loc-item").last().click();
await phone.page.waitForTimeout(900);
await phone.page.locator('[data-kind="dead_end"]').click();
await phone.page.waitForTimeout(700);
await phone.page.locator("#report-callsign").pressSequentially("Team 2", { delay: 70 });
await phone.page.locator("#report-note").pressSequentially("Slide across the trail", { delay: 55 });
await phone.page.waitForTimeout(600);
await phone.page.locator("#submit-btn").scrollIntoViewIfNeeded();
await phone.page.waitForTimeout(500);
await phone.page.locator("#submit-btn").click();

await dash.page.waitForSelector("#report-toast.is-on", { timeout: 15000 });
await dash.page.waitForTimeout(6000);
const toast = (await dash.page.locator("#report-toast").innerText()).replace(/\s+/g, " ");
const result = { phone: await phone.finish(), dash: await dash.finish(), toast, errors };
await browser.close();
console.log(JSON.stringify(result, null, 1));
