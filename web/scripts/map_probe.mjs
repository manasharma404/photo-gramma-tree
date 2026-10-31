// Why is the 2D map blank headless? Reports map state, tile requests and canvas size. (diagnostic)
import { chromium } from "playwright-core";

const browser = await chromium.launch({ channel: "msedge", headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const tiles = { ok: 0, fail: 0 };
page.on("response", (r) => { if (r.url().includes("/tiles/")) r.ok() ? tiles.ok++ : tiles.fail++; });
page.on("console", (m) => console.log("console:", m.type(), m.text().slice(0, 200)));
await page.goto("http://127.0.0.1:8000/", { waitUntil: "networkidle" });
await page.waitForTimeout(4000);
const s = await page.evaluate(() => {
  const m = window.__vortex.map;
  const c = m.getCanvas();
  return { loaded: m.loaded(), styleLoaded: m.isStyleLoaded(), tilesLoaded: m.areTilesLoaded(), zoom: m.getZoom(),
    center: m.getCenter(), canvas: [c.width, c.height], container: [m.getContainer().clientWidth, m.getContainer().clientHeight],
    layers: m.getStyle().layers.map((l) => l.id), mapReady: window.__vortex.mapReady };
});
console.log(JSON.stringify({ ...s, tiles }, null, 2));
await browser.close();
