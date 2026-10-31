// 2D map (MapLibre). No basemap from the internet: our orthophoto tiles are the base.
// No text layers (they'd need font glyphs from a server); labels live in the panel and popups.
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { STATUSES } from "./format.js";

const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
// Status meaning is carried by dash pattern AND colour (brief: not colour alone).
const DASH = { open: [1, 0], partial: [3, 2], blocked: [1, 0], unknown: [0.5, 2] };
const WIDTH = { open: 3, partial: 3, blocked: 5, unknown: 2 };

export function createMap(container, active, onSegmentClick) {
  const tiles = active?.tiles;
  const map = new maplibregl.Map({
    container,
    style: {
      version: 8,
      sources: tiles ? {
        ortho: { type: "raster", tiles: [tiles.url], tileSize: 256, minzoom: tiles.min_zoom, maxzoom: tiles.max_zoom,
                 bounds: tiles.bounds_wsen, // don't request tiles outside our map
                 attribution: "Imagery: USGS (public domain), processed by Vortex · Roads © OpenStreetMap contributors" },
      } : {},
      layers: [
        { id: "bg", type: "background", paint: { "background-color": css("--surface-2") } },
        ...(tiles ? [{ id: "ortho", type: "raster", source: "ortho" }] : []),
      ],
    },
    bounds: tiles ? [[tiles.bounds_wsen[0], tiles.bounds_wsen[1]], [tiles.bounds_wsen[2], tiles.bounds_wsen[3]]] : undefined,
    fitBoundsOptions: { padding: 40 },
    maxZoom: 22,
    attributionControl: { compact: false },
  });
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

  map.on("load", () => {
    for (const id of ["segments", "places", "checkpoints", "drawing", "results"]) {
      map.addSource(id, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    }
    for (const s of STATUSES) {
      map.addLayer({ id: `seg-${s}`, type: "line", source: "segments", filter: ["==", ["get", "status"], s],
        layout: { "line-cap": "butt" },
        paint: { "line-color": css(`--status-${s}`), "line-width": WIDTH[s], "line-dasharray": DASH[s] } });
    }
    map.addLayer({ id: "seg-verify", type: "line", source: "segments", filter: ["==", ["get", "needs_verification"], true],
      paint: { "line-color": css("--verify"), "line-width": 1, "line-gap-width": 6 } });
    map.addLayer({ id: "checkpoint-arrow", type: "line", source: "checkpoints",
      paint: { "line-color": css("--text"), "line-width": 2, "line-dasharray": [2, 1] } });
    map.addLayer({ id: "places", type: "circle", source: "places",
      paint: { "circle-radius": 6, "circle-color": css("--surface"), "circle-stroke-color": css("--text"), "circle-stroke-width": 2 } });
    map.addLayer({ id: "results-fill", type: "fill", source: "results", filter: ["==", ["geometry-type"], "Polygon"],
      paint: { "fill-color": css("--text"), "fill-opacity": 0.15 } });
    map.addLayer({ id: "results-line", type: "line", source: "results", paint: { "line-color": css("--text"), "line-width": 2 } });
    map.addLayer({ id: "drawing-line", type: "line", source: "drawing", paint: { "line-color": css("--focus"), "line-width": 2, "line-dasharray": [1, 1] } });
    map.addLayer({ id: "drawing-pt", type: "circle", source: "drawing", filter: ["==", ["geometry-type"], "Point"],
      paint: { "circle-radius": 4, "circle-color": css("--focus") } });

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
        .setHTML(`<strong>${p.id}</strong>: our map put it ${Number(p.error_h_m).toFixed(1)} m from the surveyed point`).addTo(map);
    });
    map.fire("vortex:ready");
  });
  return map;
}

export function setData(map, source, data) {
  const s = map.getSource(source);
  if (s) s.setData(data || { type: "FeatureCollection", features: [] });
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
  return STATUSES.map((s) => `<div class="legend__row"><span class="legend__swatch" style="border-top:${WIDTH[s]}px ${
    s === "partial" ? "dashed" : s === "unknown" ? "dotted" : "solid"} var(--status-${s})"></span>${s}${s === "blocked" ? " ✕" : ""}</div>`).join("")
    + `<div class="legend__row"><span class="legend__swatch" style="border-top:2px dashed var(--text)"></span>checkpoint error</div>`;
}
