// Drawing tools -> /measure API -> results. All maths happens on the server (brief section 11).
import { api } from "./api.js";
import { setData } from "./map.js";
import { renderMeasureResult, showTab } from "./panel.js";

export function initTools(map, { onStatus, onResult }) {
  let tool = null;
  let pts = [];
  const results = [];
  const buttons = document.querySelectorAll("#tools [data-tool]");
  const HINT = { span: "Click across the gap, double-click to finish", volume: "Click around the debris, double-click to finish",
    "working-space": "Click where you need space" };

  const drawPreview = () => {
    const feats = pts.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: p } }));
    if (pts.length > 1) feats.push({ type: "Feature", geometry: { type: "LineString", coordinates: tool === "volume" ? [...pts, pts[0]] : pts } });
    setData(map, "drawing", { type: "FeatureCollection", features: feats });
  };
  const select = (name) => {
    tool = name && name !== "select" ? name : null;
    pts = [];
    drawPreview();
    buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tool === (tool || "select"))));
    map.doubleClickZoom[tool ? "disable" : "enable"]();
    map.getCanvas().style.cursor = tool ? "crosshair" : "";
    onStatus(tool ? HINT[tool] || "" : "");
  };

  const run = async (kind, body, resultGeoms) => {
    onStatus("Measuring…");
    try {
      const m = await api.measure(kind, body);
      showTab("measure");
      renderMeasureResult(m);
      results.push(...resultGeoms(m));
      setData(map, "results", { type: "FeatureCollection", features: results });
      onResult?.(m);
      select(null);
    } catch (e) {
      select(null);
      onStatus(`Could not measure: ${e.message}`);
    }
  };

  buttons.forEach((b) => b.addEventListener("click", async () => {
    if (b.dataset.tool === "clear") {
      results.length = 0;
      setData(map, "results", null);
      return select(null);
    }
    if (b.dataset.tool === "landing-zones") {
      const helis = await api.helicopters();
      const names = Object.keys(helis || {});
      if (!names.length) return onStatus("No helicopter types configured");
      const choice = names.length === 1 ? names[0] : window.prompt(`Helicopter type: ${names.join(", ")}`, names[0]);
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
