// Renders docs/demo/motion/scene.html frame by frame (headless) and joins the frames with ffmpeg.
// Usage (from web/):  node scripts/motion_render.mjs <out.mp4> [stills: comma-separated seconds]
//   with stills, it only saves those frames as PNGs next to <out.mp4> (a quick look before a full render).
// The page exposes window.renderAt(seconds), DURATION and FPS; nothing depends on real time.
import { chromium } from "playwright-core";
import { createServer } from "node:http";
import { readFile, mkdir, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const web = path.resolve(here, "..");
const motion = path.resolve(web, "..", "docs", "demo", "motion");
const out = path.resolve(process.argv[2] || path.join(motion, "out", "proof.mp4"));
const stills = process.argv[3] ? process.argv[3].split(",").map(Number) : null;

const roots = [["/three/", path.join(web, "node_modules", "three")], ["/fonts/", path.join(web, "node_modules", "@fontsource")], ["/", motion]];
const types = { ".html": "text/html", ".js": "text/javascript", ".json": "application/json", ".woff2": "font/woff2", ".css": "text/css" };
const server = createServer(async (req, res) => {
  const url = decodeURIComponent(new URL(req.url, "http://x").pathname);
  const [prefix, root] = roots.find(([p]) => url.startsWith(p));
  const file = path.normalize(path.join(root, url.slice(prefix.length)));
  if (!file.startsWith(root)) { res.writeHead(403).end(); return; }
  let body;
  try { body = await readFile(file); } catch { res.writeHead(404).end(); return; }
  res.writeHead(200, { "content-type": types[path.extname(file)] || "application/octet-stream" }).end(body);
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const base = `http://127.0.0.1:${server.address().port}`;

const gpu = process.env.MOTION_GPU === "0" ? ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] : ["--use-gl=angle", "--use-angle=d3d11", "--ignore-gpu-blocklist"];
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "chrome", headless: true, args: gpu });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
await page.goto(`${base}/scene.html`);
await page.waitForFunction("window.ready === true", null, { timeout: 60000 }).catch(() => {});
if (errors.length || !(await page.evaluate("window.ready === true"))) {
  console.error("page did not get ready:", errors.join(" | ")); await browser.close(); server.close(); process.exit(1);
}
const { DURATION, FPS } = await page.evaluate("({ DURATION: window.DURATION, FPS: window.FPS })");
const stage = page.locator("#stage");
await mkdir(path.dirname(out), { recursive: true });

if (stills) {
  for (const t of stills) {
    await page.evaluate((s) => window.renderAt(s), t);
    await stage.screenshot({ path: out.replace(/\.mp4$/, `_${t.toFixed(2)}s.png`) });
  }
  console.log("stills saved:", stills.join(", "), errors.length ? "errors: " + errors.join(" | ") : "no page errors");
} else {
  const frames = path.join(path.dirname(out), "frames");
  await rm(frames, { recursive: true, force: true }); await mkdir(frames, { recursive: true });
  const n = Math.round(DURATION * FPS), t0 = Date.now();
  for (let f = 0; f < n; f++) {
    await page.evaluate((s) => window.renderAt(s), f / FPS);
    await stage.screenshot({ path: path.join(frames, `f${String(f).padStart(5, "0")}.png`) });
  }
  console.log(`${n} frames in ${((Date.now() - t0) / 1000).toFixed(1)} s`, errors.length ? "errors: " + errors.join(" | ") : "no page errors");
  const r = spawnSync("ffmpeg", ["-y", "-loglevel", "error", "-framerate", String(FPS), "-i", path.join(frames, "f%05d.png"),
    "-c:v", "libx264", "-crf", "15", "-preset", "slow", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out], { stdio: "inherit" });
  if (r.status !== 0) { console.error("ffmpeg failed"); process.exitCode = 1; } else { await rm(frames, { recursive: true, force: true }); console.log("wrote", out); }
}
await browser.close(); server.close();
