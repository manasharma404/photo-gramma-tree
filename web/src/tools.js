// Drawing tools -> /measure API -> results. All maths happens on the server (brief section 11).
import { api } from "./api.js";
import { setData } from "./map.js";
import { renderMeasureResult, showTab } from "./panel.js";

export function initTools(map, onStatus) {
  let tool = null;
  let pts = [];
  const results = [];
  const buttons = document.querySelectorAll("#tools [data-tool]");

  const drawPreview = () => {
    const feats = pts.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: p } }));
    if (pts.length > 1) feats.push({ type: "Feature", geometry: { type: "LineString", coordinates: tool === "volume" ? [...pts, pts[0]] : pts } });
    setData(map, "drawing", { type: "FeatureCollection", features: feats });
  };
  const select = (name) => {
    tool = tool === name ? null : name;
    pts = [];
    drawPreview();
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tool === tool)));
    map.doubleClickZoom[tool ? "disable" : "enable"]();
    onStatus(tool ? `Tool: ${tool}` : "");
  };

  const run = async (kind, body, resultGeoms) => {
    onStatus(`Measuring ${kind}…`);
    try {
      const m = await api.measure(kind, body);
      renderMeasureResult(m);
      showTab("measure");
      results.push(...resultGeoms(m));
      setData(map, "results", { type: "FeatureCollection", features: results });
      onStatus("");
    } catch (e) {
      onStatus(`Could not measure: ${e.message}`);
    }
    select(null);
  };

  buttons.forEach((b) => b.addEventListener("click", async () => {
    if (b.dataset.tool === "clear") {
      results.length = 0;
      setData(map, "results", null);
      select(null);
      return;
    }
    if (b.dataset.tool === "landing-zones") {
      const helis = await api.helicopters();
      const names = Object.keys(helis || {});
      if (!names.length) return onStatus("No helicopter types configured");
      const choice = window.prompt(`Helicopter type: ${names.join(", ")}`, names[0]);
      if (!choice) return;
      return run("landing-zones", { helicopter: choice },
        (m) => m.result.candidates.map((c) => ({ type: "Feature", geometry: c.polygon, properties: {} })));
    }
    select(b.dataset.tool);
  }));

  map.on("click", (e) => {
    if (!tool) return;
    pts.push([e.lngLat.lng, e.lngLat.lat]);
    drawPreview();
    if (tool === "working-space") {
      run("working-space", { geometry: { type: "Point", coordinates: pts[0] } },
        (m) => [{ type: "Feature", geometry: m.result.rectangle_polygon, properties: {} }]);
    }
  });
  map.on("dblclick", (e) => {
    if (tool === "span" && pts.length >= 2) {
      const line = { type: "LineString", coordinates: pts };
      run("span", { geometry: line }, () => [{ type: "Feature", geometry: line, properties: {} }]);
    } else if (tool === "volume" && pts.length >= 3) {
      const poly = { type: "Polygon", coordinates: [[...pts, pts[0]]] };
      run("volume", { geometry: poly }, () => [{ type: "Feature", geometry: poly, properties: {} }]);
    }
    e.preventDefault();
  });
}
