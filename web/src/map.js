// 2D map (MapLibre). No basemap from the internet: our orthophoto tiles are the base.
// No text layers (they'd need font glyphs from a server); labels live in the panel and popups.
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { STATUSES } from "./format.js";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
// Status meaning is carried by dash pattern AND colour (brief: never colour alone); blocked also gets ✕ marks.
const DASH = { open: [1, 0], partial: [3, 2], blocked: [1, 0], unknown: [0.6, 1.8] };
const WIDTH = { open: 3.5, partial: 3.5, blocked: 5, unknown: 2.5 };

// Layer groups the Layers panel can toggle.
export const LAYER_GROUPS = {
  ortho: { label: "Orthomosaic", layers: ["ortho"] },
  roads: { label: "Roads by status", layers: ["seg-halo", ...STATUSES.map((s) => `seg-${s}`), "seg-blocked-x", "seg-verify"] },
  places: { label: "Places", layers: ["places"] },
  checkpoints: { label: "Checkpoint errors", layers: ["checkpoint-halo", "checkpoint-arrow", "checkpoint-end"] },
  results: { label: "Measurements", layers: ["results-fill", "results-line"] },
};

function crossIcon(color, halo) {
  const s = 22, c = document.createElement("canvas");
  c.width = c.height = s;
  const g = c.getContext("2d");
  g.lineCap = "round";
  for (const [w, col] of [[7, halo], [3.2, color]]) {
    g.strokeStyle = col;
    g.lineWidth = w;
    g.beginPath(); g.moveTo(5, 5); g.lineTo(s - 5, s - 5); g.moveTo(s - 5, 5); g.lineTo(5, s - 5); g.stroke();
  }
  return g.getImageData(0, 0, s, s);
}

export function createMap(container, active, onSegmentClick) {
  const tiles = active?.tiles;
  const map = new maplibregl.Map({
    container,
    style: {
      version: 8,
      sources: tiles ? {
        ortho: { type: "raster", tiles: [tiles.url], tileSize: 256, minzoom: tiles.min_zoom, maxzoom: tiles.max_zoom,
                 bounds: tiles.bounds_wsen, // don't request tiles outside our map
                 attribution: "Imagery: USGS (public domain), processed by Project Typhon · Roads © OpenStreetMap contributors" },
      } : {},
      layers: [
        { id: "bg", type: "background", paint: { "background-color": css("--stone") } },
        ...(tiles ? [{ id: "ortho", type: "raster", source: "ortho" }] : []),
      ],
    },
    bounds: tiles ? [[tiles.bounds_wsen[0], tiles.bounds_wsen[1]], [tiles.bounds_wsen[2], tiles.bounds_wsen[3]]] : undefined,
    fitBoundsOptions: { padding: 60 },
    maxZoom: 22,
    attributionControl: { compact: true },
  });
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "bottom-right");

  map.on("load", () => {
    map.addImage("x-blocked", crossIcon(css("--status-blocked"), css("--halo")));
    for (const id of ["segments", "places", "checkpoints", "drawing", "results"]) {
      map.addSource(id, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    }
    map.addLayer({ id: "seg-halo", type: "line", source: "segments", layout: { "line-cap": "round", "line-join": "round" },
      paint: { "line-color": css("--halo"), "line-width": 8 } });
    for (const s of STATUSES) {
      map.addLayer({ id: `seg-${s}`, type: "line", source: "segments", filter: ["==", ["get", "status"], s],
        layout: { "line-join": "round" },
        paint: { "line-color": css(`--status-${s}`), "line-width": WIDTH[s], "line-dasharray": DASH[s] } });
    }
    map.addLayer({ id: "seg-blocked-x", type: "symbol", source: "segments", filter: ["==", ["get", "status"], "blocked"],
      layout: { "symbol-placement": "line", "symbol-spacing": 70, "icon-image": "x-blocked", "icon-allow-overlap": true } });
    map.addLayer({ id: "seg-verify", type: "line", source: "segments", filter: ["==", ["get", "needs_verification"], true],
      paint: { "line-color": css("--verify"), "line-width": 1.2, "line-gap-width": 9, "line-opacity": 0.7 } });
    map.addLayer({ id: "checkpoint-halo", type: "line", source: "checkpoints", paint: { "line-color": css("--halo"), "line-width": 6 } });
    map.addLayer({ id: "checkpoint-arrow", type: "line", source: "checkpoints",
      paint: { "line-color": css("--ocean"), "line-width": 2.5, "line-dasharray": [2, 1] } });
    map.addLayer({ id: "checkpoint-end", type: "circle", source: "checkpoints",
      paint: { "circle-radius": 5, "circle-color": css("--ocean"), "circle-stroke-color": css("--halo"), "circle-stroke-width": 2 } });
    map.addLayer({ id: "places", type: "circle", source: "places",
      paint: { "circle-radius": 7, "circle-color": css("--surface"), "circle-stroke-color": css("--forest"), "circle-stroke-width": 3 } });
    map.addLayer({ id: "results-fill", type: "fill", source: "results", filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": css("--sage"), "fill-opacity": 0.35 } });
    map.addLayer({ id: "results-line", type: "line", source: "results", paint: { "line-color": css("--forest"), "line-width": 2.5 } });
    map.addLayer({ id: "drawing-line", type: "line", source: "drawing", paint: { "line-color": css("--ocean"), "line-width": 2.5, "line-dasharray": [1, 1] } });
    map.addLayer({ id: "drawing-pt", type: "circle", source: "drawing", filter: ["==", ["geometry-type"], "Point"],
      paint: { "circle-radius": 5, "circle-color": css("--ocean"), "circle-stroke-color": css("--halo"), "circle-stroke-width": 2 } });

    for (const s of STATUSES) {
      map.on("click", `seg-${s}`, (e) => onSegmentClick?.(e.features[0].properties.segment_id));
      map.on("mouseenter", `seg-${s}`, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", `seg-${s}`, () => (map.getCanvas().style.cursor = ""));
    }
    map.on("click", "places", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(`<strong>${p.name || p.place_id}</strong><br>${p.kind}`).addTo(map);
    });
    map.on("click", "checkpoint-arrow", (e) => {
      const p = e.features[0].properties;
      new maplibregl.Popup().setLngLat(e.lngLat)
        .setHTML(`<strong>${p.id}</strong>: our map placed this target ${Number(p.error_h_m).toFixed(1)} m from its surveyed position`).addTo(map);
    });
    map.fire("vortex:ready");
  });
  return map;
}

export function setData(map, source, data) {
  const s = map.getSource(source);
  if (s) s.setData(data || { type: "FeatureCollection", features: [] });
}

export function setGroupVisible(map, group, visible) {
  for (const id of LAYER_GROUPS[group].layers) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", visible ? "visible" : "none");
  }
}

/** Segments with the selected vehicle's status and reasons merged in from /advisor/state. */
export function segmentsForVehicle(segments, state, vehicle) {
  const byId = Object.fromEntries((state?.segments || []).map((s) => [s.segment_id, s]));
  return {
    type: "FeatureCollection",
    features: (segments?.features || []).map((f) => {
      const st = byId[f.properties.segment_id];
      return { ...f, properties: { ...f.properties,
        status: st?.status_by_mode?.[vehicle] || "unknown",
        needs_verification: Boolean(st?.needs_verification), source: st?.source || null } };
    }),
  };
}

export function legendHTML() {
  const style = { open: "solid", partial: "dashed", blocked: "solid", unknown: "dotted" };
  return STATUSES.map((s) => `<div class="legend__row"><span class="legend__swatch" style="border-top:${WIDTH[s]}px ${style[s]} var(--status-${s})"></span>${
    s === "blocked" ? "Blocked ✕" : s[0].toUpperCase() + s.slice(1)}</div>`).join("")
    + `<div class="legend__row"><span class="legend__swatch" style="border-top:2px dashed var(--ocean)"></span>Checkpoint error</div>`;
}
