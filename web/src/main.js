import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/space-grotesk/latin-400.css";
import "@fontsource/space-grotesk/latin-500.css";
import "./styles/tokens.css";
import "./styles/app.css";
import { api } from "./api.js";
import { VEHICLES, esc } from "./format.js";
import { mountIcons } from "./icons.js";
import { LAYER_GROUPS, createMap, legendHTML, segmentsForVehicle, setData, setGroupVisible } from "./map.js";
import { accuracyMiniHTML, initTabs, renderAccuracy, renderActNow, renderMeasureIntro, renderReports, renderRoads,
  renderSegmentDetail, showTab } from "./panel.js";
import { initTools } from "./tools.js";

const $ = (id) => document.getElementById(id);
const app = { vehicle: "foot", segments: null, state: null, three: null, mapReady: false };
window.__vortex = app; // inspection handle for the headless check (scripts/screenshot.mjs)

// Data labels (hard rule 6): public data is never presented as our footage.
const DATA_LABEL = {
  southfork: "USGS public data · South Fork debris flow, California, 30 Apr 2024 · not our footage",
  wayanad: "Scenario reconstructed from reports · not drone-measured",
  neo2: "Our footage · DJI Neo 2",
};
const labelFor = (project) => Object.entries(DATA_LABEL).find(([k]) => project?.startsWith(k))?.[1] || "";
const vehicleLabel = () => VEHICLES.find(([k]) => k === app.vehicle)[1];
const status = (msg) => ($("statusline").textContent = msg || "");

async function boot() {
  mountIcons();
  initTabs();
  document.addEventListener("click", (e) => {
    const go = e.target.closest("[data-goto]");
    if (go) showTab(go.dataset.goto);
  });
  renderMeasureIntro();
  $("legend").innerHTML = legendHTML();

  const [active, health] = await Promise.all([api.active(), api.health()]);
  const off = $("offline");
  off.dataset.state = !health ? "down" : health.internet_reachable ? "online" : "offline";
  $("offline-text").textContent = !health ? "API not reachable" : health.internet_reachable ? "Online (not needed)" : "Offline mode";

  if (!active) {
    $("site").innerHTML = `<option>No map processed yet</option>`;
    $("tab-act").innerHTML = `<p class="empty">No map is active. Process a survey, then run <code>python -m pipeline.activate</code>.</p>`;
    return;
  }
  app.project = active.project;
  $("site").innerHTML = `<option>${esc(prettySite(active.project))}</option>`;
  $("dataset").textContent = labelFor(active.project);
  $("dataset").title = `run ${active.run_id}`;
  $("freshness").textContent = new Date(active.set_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });

  $("vehicle").innerHTML = VEHICLES.map(([k, l]) => `<button role="radio" data-v="${k}" aria-checked="${k === app.vehicle}">${l}</button>`).join("");
  $("vehicle").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    app.vehicle = b.dataset.v;
    $("vehicle").querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    refresh();
  }));

  const map = createMap($("map"), active, openSegment);
  app.map = map;
  initTools(map, { onStatus: status, onResult: (m) => m.type === "span" && renderProfile(m) });
  initLayers(active);

  // Panels don't wait for the map to draw (a hidden or slow map must not leave them empty).
  const [segments, places, checkpoints, spec] = await Promise.all([
    api.layer("segments"), api.layer("places"), api.layer("checkpoints"), api.spec()]);
  app.segments = segments;
  app.spec = spec;
  renderAccuracy(spec);
  $("accuracy-mini").innerHTML = accuracyMiniHTML(spec);
  renderOverview(active);
  await loadAdvisor();

  const fillMap = () => {
    app.mapReady = true;
    setData(map, "places", places);
    setData(map, "checkpoints", checkpoints);
    refresh();
  };
  if (map.getSource("segments")) fillMap();
  else map.once("vortex:ready", fillMap);

  init3D(active);
}

function prettySite(p) {
  if (p.startsWith("southfork")) return `South Fork debris flow (${p.replace("southfork_", "").replace("_", "-").toUpperCase()})`;
  if (p.startsWith("wayanad")) return "Wayanad scenario";
  return p;
}

async function loadAdvisor() {
  const [state, priorities, access, reports] = await Promise.all([
    api.state(app.project), api.priorities(app.project), api.access(app.project), api.reports(app.project)]);
  Object.assign(app, { state, priorities, access });
  renderReports(reports);
  refresh();
}

function refresh() {
  const fc = segmentsForVehicle(app.segments, app.state, app.vehicle);
  app.fc = fc;
  if (app.mapReady) setData(app.map, "segments", fc);
  renderRoads(fc, vehicleLabel(), openSegment);
  renderActNow({ priorities: app.priorities, access: app.access, fc, spec: app.spec, vehicle: app.vehicle, vehicleLabel: vehicleLabel() });
  app.three?.setRoads({ ...fc, features: fc.features.filter((f) => f.properties.measured) });
}

function openSegment(id) {
  const seg = app.fc?.features.find((f) => f.properties.segment_id === id);
  if (!seg) return;
  showTab("roads");
  renderSegmentDetail(seg, app.state?.segments?.find((s) => s.segment_id === id));
  $("back-roads").addEventListener("click", () => renderRoads(app.fc, vehicleLabel(), openSegment));
}

function initLayers(active) {
  $("layer-list").innerHTML = Object.entries(LAYER_GROUPS).map(([k, g]) => `<label class="layer"><span>${g.label}</span>
      <span class="switch"><input type="checkbox" data-layer="${k}" checked ${k === "ortho" && !active.tiles ? "disabled" : ""}><span></span></span></label>`).join("");
  $("layer-list").querySelectorAll("input").forEach((i) => i.addEventListener("change", () => setGroupVisible(app.map, i.dataset.layer, i.checked)));
}

function renderOverview(active) {
  $("card-overview").innerHTML = `<header><span>Overview</span></header>
    <div class="label-public">${esc(labelFor(active.project))}</div>
    <div class="muted">${esc(prettySite(active.project))}. Mapped from drone images without ground control; every number on screen comes from a run on this laptop.</div>`;
  if (active.terrain) $("thumb-3d").style.backgroundImage = `url(${active.terrain.url}${active.terrain.thumb || active.terrain.texture.file})`;
  else $("thumb-3d").innerHTML = `<p class="empty">No 3D terrain for this run yet</p>`;
  $("profile-body").innerHTML = `<p class="muted">Draw a span across a gap to see its height profile here.</p>`;
}

function renderProfile(m) {
  const p = m.result.profile;
  if (!p) return;
  const W = 300, H = 100, pad = 4;
  const zs = p.height_m.filter((v) => v != null);
  const zmin = Math.min(...zs), zmax = Math.max(...zs), dmax = p.distance_m[p.distance_m.length - 1] || 1;
  const x = (d) => pad + (d / dmax) * (W - 2 * pad), y = (z) => H - pad - ((z - zmin) / (zmax - zmin || 1)) * (H - 2 * pad);
  const path = p.distance_m.map((d, i) => p.height_m[i] == null ? "" : `${i ? "L" : "M"}${x(d).toFixed(1)},${y(p.height_m[i]).toFixed(1)}`).join("");
  const span = m.result.span_m;
  $("profile-body").innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" height="100" role="img" aria-label="Height profile">
      <path d="${path} L${x(dmax)},${H} L${x(0)},${H}Z" fill="var(--stone)"/><path d="${path}" fill="none" stroke="var(--forest)" stroke-width="1.5"/>
      ${span ? `<line x1="${x(p.bank_a_m)}" x2="${x(p.bank_b_m)}" y1="${y(m.result.bank_a_height_m)}" y2="${y(m.result.bank_b_height_m)}" stroke="var(--ocean)" stroke-dasharray="4 3"/>` : ""}
    </svg><div class="muted">${span ? `Span ${span.toFixed(1)} m · bed ${m.result.bed_elevation_m.toFixed(1)} m` : esc(m.result.note || "")}</div>`;
}

function init3D(active) {
  const btn3d = $("btn-3d");
  const buttons = document.querySelectorAll("[data-view]");
  if (!active.terrain) { btn3d.disabled = true; btn3d.title = "No 3D terrain exported for this run yet"; }
  const setView = async (v) => {
    buttons.forEach((b) => b.setAttribute("aria-checked", String(b.dataset.view === v)));
    const on = v === "3d";
    $("three").hidden = !on; $("map").hidden = on; $("exaggeration").hidden = !on;
    $("layers").hidden = on; $("tools").hidden = on;
    if (on && !app.three) {
      status("Loading 3D terrain…");
      const { createThreeView } = await import("./three-view.js");
      app.three = await createThreeView($("three"), active.terrain, active.terrain.url);
      app.three.setRoads({ ...app.fc, features: (app.fc?.features || []).filter((f) => f.properties.measured) });
      status("");
    }
    if (!on) app.map.resize();
  };
  buttons.forEach((b) => b.addEventListener("click", () => !b.disabled && setView(b.dataset.view)));
  $("card-3d").addEventListener("click", () => active.terrain && setView("3d"));
  $("exag").addEventListener("input", (e) => {
    $("exag-value").textContent = e.target.value;
    app.three?.setExaggeration(Number(e.target.value));
  });
}

boot();
