// Does headless Edge have WebGL, and does the map finish loading? (diagnostic)
import { chromium } from "playwright-core";

for (const args of [[], ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"], ["--use-gl=angle", "--use-angle=d3d11", "--ignore-gpu-blocklist"]]) {
  const browser = await chromium.launch({ channel: "msedge", headless: true, args });
  const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
  const r = await page.evaluate(() => {
    const c = document.createElement("canvas");
    const gl = c.getContext("webgl2") || c.getContext("webgl");
    const dbg = gl && gl.getExtension("WEBGL_debug_renderer_info");
    return { webgl: !!gl, renderer: gl && dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null };
  });
  console.log(JSON.stringify({ args, ...r }));
  await browser.close();
}
