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
  // the route for the chosen vehicle: solid when open, dashed through roads not seen, red where it is blocked
  map.addSource("demo-route", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({ id: "demo-route-casing", type: "line", source: "demo-route", filter: ["==", ["get", "part"], "path"],
    layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#FFFFFF", "line-width": 11, "line-opacity": 0.95 } });
  map.addLayer({ id: "demo-route-solid", type: "line", source: "demo-route", filter: ["all", ["==", ["get", "part"], "path"], ["!=", ["get", "kind"], "unverified"]],
    layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": "#24321F", "line-width": 5.5 } });
  map.addLayer({ id: "demo-route-dash", type: "line", source: "demo-route", filter: ["all", ["==", ["get", "part"], "path"], ["==", ["get", "kind"], "unverified"]],
    paint: { "line-color": "#24321F", "line-width": 5, "line-dasharray": [1.2, 1.2] } });
  map.addLayer({ id: "demo-route-need", type: "line", source: "demo-route", filter: ["==", ["get", "part"], "need"],
    layout: { "line-cap": "round" }, paint: { "line-color": "#B3261E", "line-width": 9, "line-opacity": 0.85 } });
  map.addLayer({ id: "demo-route-ends", type: "circle", source: "demo-route", filter: ["==", ["get", "part"], "end"],
    paint: { "circle-radius": 7, "circle-color": "#B5D334", "circle-stroke-color": "#24321F", "circle-stroke-width": 3 } });
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
    showRoute(route, segsById) {
      const fs = [];
      if (route) {
        fs.push({ type: "Feature", geometry: { type: "LineString", coordinates: route.coords }, properties: { part: "path", kind: route.kind } });
        for (const id of route.blocked) { const g = segsById?.[id]; if (g) fs.push({ type: "Feature", geometry: g, properties: { part: "need" } }); }
        fs.push({ type: "Feature", geometry: { type: "Point", coordinates: route.coords[0] }, properties: { part: "end" } });
        fs.push({ type: "Feature", geometry: { type: "Point", coordinates: route.coords[route.coords.length - 1] }, properties: { part: "end" } });
      }
      map.getSource("demo-route")?.setData({ type: "FeatureCollection", features: fs });
    },
    showFlight(plan) { map.getSource("demo-flight")?.setData(plan ? plan.geojson : { type: "FeatureCollection", features: [] }); },
    setVisible(on) {
      for (const id of ["demo-blur-fill", "demo-blur-line", "demo-flight-line", "demo-flight-pt", "demo-route-casing", "demo-route-solid", "demo-route-dash", "demo-route-need", "demo-route-ends"]) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
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

/**
 * The best way from the base to a point for the chosen vehicle, over the road network on the map (each road's
 * `status` is already the chosen vehicle's). Three tries, in order: open or partly open roads only; then also roads
 * not seen; then also blocked roads, at a high cost, so the result names what has to be cleared.
 * Returns { kind: "ok" | "unverified" | "cut", coords, length_m, blocked: [segment ids], unknown: n } or null.
 */
export function planRoute(fc, from, to) {
  const key = (c) => `${c[0].toFixed(5)},${c[1].toFixed(5)}`;
  const nodes = new Map(), adj = new Map();
  const node = (c) => { const k = key(c); if (!nodes.has(k)) { nodes.set(k, c); adj.set(k, []); } return k; };
  const len = (cs) => { let s = 0; for (let i = 1; i < cs.length; i++) s += hav(cs[i - 1], cs[i]); return s; };
  for (const f of fc?.features || []) {
    const parts = f.geometry.type === "MultiLineString" ? f.geometry.coordinates : [f.geometry.coordinates];
    for (const cs of parts) {
      if (cs.length < 2) continue;
      const a = node(cs[0]), b = node(cs[cs.length - 1]);
      const e = { id: f.properties.segment_id, st: f.properties.status, len: f.properties.length_m || len(cs), cs };
      adj.get(a).push({ to: b, e, fwd: true });
      adj.get(b).push({ to: a, e, fwd: false });
    }
  }
  if (!nodes.size) return null;
  const nearest = (p) => { let best = null, d = Infinity; for (const [k, c] of nodes) { const x = hav(p, c); if (x < d) { d = x; best = k; } } return best; };
  const s = nearest(from), t = nearest(to);
  const COST = [{ open: 1, partial: 1.6 }, { open: 1, partial: 1.6, unknown: 4 }, { open: 1, partial: 1.6, unknown: 4, blocked: 60 }];
  const KIND = ["ok", "unverified", "cut"];
  for (let pass = 0; pass < 3; pass++) {
    const w = COST[pass];
    const dist = new Map([[s, 0]]), prev = new Map(), done = new Set();
    const heap = [[0, s]];
    while (heap.length) {
      heap.sort((x, y) => x[0] - y[0]);
      const [d, u] = heap.shift();
      if (done.has(u)) continue;
      done.add(u);
      if (u === t) break;
      for (const { to, e, fwd } of adj.get(u)) {
        const c = w[e.st];
        if (c === undefined || done.has(to)) continue;
        const nd = d + e.len * c;
        if (nd < (dist.get(to) ?? Infinity)) { dist.set(to, nd); prev.set(to, { from: u, e, fwd }); heap.push([nd, to]); }
      }
    }
    if (!dist.has(t)) continue;
    const coords = [], blocked = [];
    let unknown = 0, partial = 0, length_m = 0, v = t;
    const steps = [];
    while (v !== s) { const p = prev.get(v); steps.push(p); v = p.from; }
    steps.reverse().forEach(({ e, fwd }) => {
      const cs = fwd ? e.cs : [...e.cs].reverse();
      coords.push(...(coords.length ? cs.slice(1) : cs));
      length_m += e.len;
      if (e.st === "blocked") blocked.push(e.id);
      if (e.st === "unknown") unknown += 1;
      if (e.st === "partial") partial += 1;
    });
    return { kind: KIND[pass], coords, length_m, blocked, unknown, partial };
  }
  return null;
}

function hav(a, b) {
  const R = 6371000, toR = Math.PI / 180;
  const dLat = (b[1] - a[1]) * toR, dLon = (b[0] - a[0]) * toR;
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * toR) * Math.cos(b[1] * toR) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}
