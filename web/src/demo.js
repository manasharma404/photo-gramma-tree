// The map's DEMO scenario: real OpenStreetMap roads with SIMULATED blockages, a blurred patch and trapped people
// (scripts/build_demo_scenario.py, served by GET /advisor/demo/scenario). Everything simulated says so on screen.
// This module draws the extras (people, blockages, the blurred patch, a re-fly plan) and plans the re-fly.
import maplibregl from "maplibre-gl";
import { esc } from "./format.js";

export const PASS_LABEL = { fire_truck: "Fire truck", ambulance: "Ambulance", jeep: "Jeep", foot: "On foot" };
const KIND_ICON = {
  debris: '<path d="M3 17h18M6 17l3-6 3 3 3-5 3 8" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>',
  narrowed: '<path d="M4 4v16M20 4v16M9 12h6M11 9l-2 3 2 3M13 9l2 3-2 3" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  bridge: '<path d="M2 15h20M5 15v4M19 15v4M2 11c4-4 16-4 20 0M9 13l2-3 2 2" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  flood: '<path d="M2 9c3-2 5 2 8 0s5 2 8 0 3 0 4 0M2 15c3-2 5 2 8 0s5 2 8 0 3 0 4 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
};
const icon = (kind) => `<svg viewBox="0 0 24 24" aria-hidden="true">${KIND_ICON[kind] || ""}</svg>`;

function hatch(color) {
  const s = 12, c = document.createElement("canvas");
  c.width = c.height = s;
  const g = c.getContext("2d");
  g.strokeStyle = color; g.lineWidth = 1.6;
  g.beginPath(); g.moveTo(0, s); g.lineTo(s, 0); g.moveTo(-s / 2, s / 2); g.lineTo(s / 2, -s / 2); g.moveTo(s / 2, s + s / 2); g.lineTo(s + s / 2, s / 2); g.stroke();
  return g.getImageData(0, 0, s, s);
}

/** Add the demo's layers and markers; returns a handle to recolour them and to show a re-fly plan. */
export function addDemoLayers(map, demo, { onBlockage, onPeople } = {}) {
  map.addImage("blur-hatch", hatch("rgba(42, 78, 168, 0.55)"));
  map.addSource("demo-blur", { type: "geojson", data: { type: "FeatureCollection",
    features: demo.blur_zones.map((z) => ({ type: "Feature", geometry: z.polygon, properties: { id: z.id } })) } });
  map.addSource("demo-flight", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({ id: "demo-blur-fill", type: "fill", source: "demo-blur", paint: { "fill-pattern": "blur-hatch", "fill-opacity": 0.9 } }, "seg-halo");
  map.addLayer({ id: "demo-blur-line", type: "line", source: "demo-blur", paint: { "line-color": "#2A4EA8", "line-width": 1.8, "line-dasharray": [2, 2] } });
  map.addLayer({ id: "demo-flight-line", type: "line", source: "demo-flight", layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#7A9A1C", "line-width": 2.6 } });
  map.addLayer({ id: "demo-flight-pt", type: "circle", source: "demo-flight", filter: ["==", ["geometry-type"], "Point"],
    paint: { "circle-radius": 5, "circle-color": "#B5D334", "circle-stroke-color": "#24321F", "circle-stroke-width": 2 } });

  const markers = [];
  for (const b of demo.blockages) {
    const el = document.createElement("button");
    el.className = `dmk dmk--block dmk--${b.kind}`;
    el.innerHTML = `${icon(b.kind)}<span><b>${esc(b.title)}</b><i>${b.passes.length ? esc(b.passes.map((m) => PASS_LABEL[m]).join(" · ")) + " only" : "Nobody passes"}</i></span>`;
    el.title = b.why;
    el.addEventListener("click", (e) => { e.stopPropagation(); onBlockage?.(b); });
    markers.push({ kind: "block", data: b, m: new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat(b.lonlat).addTo(map) });
  }
  for (const p of demo.people) {
    const el = document.createElement("button");
    el.className = "dmk dmk--people";
    el.innerHTML = `<b>${p.count}</b><span>${esc(p.name)}</span>`;
    el.addEventListener("click", (e) => { e.stopPropagation(); onPeople?.(p); });
    markers.push({ kind: "people", data: p, el, m: new maplibregl.Marker({ element: el, anchor: "center" }).setLngLat(p.lonlat).addTo(map) });
  }
  const zone = demo.blur_zones[0];
  let zoneEl = null;
  if (zone) {
    zoneEl = document.createElement("div");
    zoneEl.className = "dmk dmk--blur";
    zoneEl.innerHTML = `<span><b>Blurred photos</b><i>${zone.segments.length} roads not seen</i></span>`;
    const c = centroid(zone.polygon.coordinates[0]);
    new maplibregl.Marker({ element: zoneEl, anchor: "center" }).setLngLat(c).addTo(map);
  }

  return {
    /** People markers: red = cut off for this vehicle, amber = unverified, green = reachable. */
    recolour(access, vehicle) {
      const byId = Object.fromEntries((access?.places || []).map((p) => [p.place_id, p]));
      for (const mk of markers.filter((x) => x.kind === "people")) {
        const r = byId[mk.data.place_id]?.reachable?.[vehicle];
        mk.el.dataset.state = r === false ? "cut" : r == null ? "unverified" : "ok";
      }
    },
    showFlight(plan) { map.getSource("demo-flight")?.setData(plan ? plan.geojson : { type: "FeatureCollection", features: [] }); },
    setVisible(on) {
      for (const id of ["demo-blur-fill", "demo-blur-line", "demo-flight-line", "demo-flight-pt"]) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
      markers.forEach((x) => (x.m.getElement().style.display = on ? "" : "none"));
      if (zoneEl) zoneEl.style.display = on ? "" : "none";
    },
  };
}

function centroid(ring) {
  const n = ring.length - 1;
  return [ring.slice(0, n).reduce((s, c) => s + c[0], 0) / n, ring.slice(0, n).reduce((s, c) => s + c[1], 0) / n];
}

/**
 * A lawnmower re-fly over the blurred patch. ESTIMATE from stated assumptions (shown with the result):
 * 70 m above ground, camera footprint about 120 m wide, 70 % side overlap -> lines 36 m apart, 6 m/s,
 * a photo every 2 s. These are flight-planning defaults, not measurements.
 */
export function planReflight(zone, opts = {}) {
  const ring = zone.polygon.coordinates[0];
  const [lon0, lat0] = centroid(ring);
  const kx = 111320 * Math.cos((lat0 * Math.PI) / 180), ky = 111320;
  const P = ring.map(([lon, lat]) => [(lon - lon0) * kx, (lat - lat0) * ky]);
  const height = opts.height_m ?? 70, footprint = opts.footprint_m ?? 120, overlap = opts.side_overlap ?? 0.7, speed = opts.speed_ms ?? 6;
  const spacing = footprint * (1 - overlap);
  const ys = P.map((p) => p[1]);
  const lines = [];
  let flip = false;
  for (let y = Math.min(...ys) + spacing / 2; y < Math.max(...ys); y += spacing) {
    const xs = [];
    for (let i = 0; i < P.length - 1; i++) {
      const [a, b] = [P[i], P[i + 1]];
      if ((a[1] <= y && b[1] > y) || (b[1] <= y && a[1] > y)) xs.push(a[0] + ((y - a[1]) / (b[1] - a[1])) * (b[0] - a[0]));
    }
    xs.sort((p, q) => p - q);
    for (let k = 0; k + 1 < xs.length; k += 2) {
      const seg = [[xs[k] - spacing / 2, y], [xs[k + 1] + spacing / 2, y]];
      lines.push(flip ? seg.reverse() : seg);
      flip = !flip;
    }
  }
  const path = lines.flat();
  let length = 0;
  for (let i = 1; i < path.length; i++) length += Math.hypot(path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]);
  const toLL = ([x, y]) => [lon0 + x / kx, lat0 + y / ky];
  const geojson = { type: "FeatureCollection", features: [
    { type: "Feature", geometry: { type: "LineString", coordinates: path.map(toLL) }, properties: { kind: "flight" } },
    { type: "Feature", geometry: { type: "Point", coordinates: toLL(path[0]) }, properties: { kind: "start" } },
  ] };
  const seconds = length / speed;
  return { geojson, lines: lines.length, length_m: Math.round(length), minutes: Math.max(1, Math.round(seconds / 60)),
    photos: Math.round(seconds / 2), assumptions: `${height} m above ground · lines ${Math.round(spacing)} m apart (70 % overlap) · ${speed} m/s · a photo every 2 s` };
}
