import "./styles/tokens.css";
import "./styles/app.css";
import { api } from "./api.js";
import { VEHICLES, esc } from "./format.js";
import { createMap, legendHTML, segmentsForVehicle, setData } from "./map.js";
import { initTabs, renderAccuracy, renderActNow, renderMeasureIntro, renderReports, renderRoads,
  renderSegmentDetail, showTab } from "./panel.js";
import { initTools } from "./tools.js";

const $ = (id) => document.getElementById(id);
const app = { vehicle: "foot", segments: null, state: null, three: null };
window.__vortex = app; // inspection handle for the headless check (scripts/screenshot.mjs)

// Data labels (hard rule 6): public data is never presented as our footage.
const DATA_LABEL = {
  southfork: "USGS public data (South Fork debris flow, 30 Apr 2024), not our footage",
  wayanad: "Scenario reconstructed from reports, not drone-measured",
  neo2: "Our footage (DJI Neo 2)",
};
const labelFor = (project) => Object.entries(DATA_LABEL).find(([k]) => project?.startsWith(k))?.[1] || "";

const status = (msg) => ($("statusline").textContent = msg || "");

async function boot() {
  initTabs();
  renderMeasureIntro();
  $("legend").innerHTML = legendHTML();

  const [active, health] = await Promise.all([api.active(), api.health()]);
  $("offline").textContent = health ? (health.internet_reachable ? "Internet reachable" : "Offline: running on this laptop") : "API not reachable";

  if (!active) {
    $("site").innerHTML = `<option>No map processed yet</option>`;
    $("tab-act").innerHTML = `<p class="empty">No run is active. Process a map, then run <code>python -m pipeline.activate</code>.</p>`;
    return;
  }
  app.project = active.project;
  $("site").innerHTML = `<option>${esc(active.project)}</option>`;
  $("data-label").textContent = labelFor(active.project);

  $("vehicle").innerHTML = VEHICLES.map(([k, l]) =>
    `<button role="radio" data-v="${k}" aria-checked="${k === app.vehicle}">${l}</button>`).join("");
  $("vehicle").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    app.vehicle = b.dataset.v;
    $("vehicle").querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    refreshRoads();
  }));

  const map = createMap($("map"), active, (segId) => openSegment(segId));
  app.map = map;
  map.on("mousemove", (e) => status(`${e.lngLat.lat.toFixed(6)}, ${e.lngLat.lng.toFixed(6)} · run ${active.run_id}`));
  initTools(map, status);

  // Panels don't wait for the map to draw (a hidden or slow map must not leave them empty).
  const [segments, places, checkpoints, spec] = await Promise.all([
    api.layer("segments"), api.layer("places"), api.layer("checkpoints"), api.spec()]);
  app.segments = segments;
  renderAccuracy(spec);
  $("freshness").textContent = freshness(spec, active);
  await loadAdvisor();

  const fillMap = () => {
    app.mapReady = true;
    setData(map, "places", places);
    setData(map, "checkpoints", checkpoints);
    refreshRoads();
  };
  if (map.getSource("segments")) fillMap();
  else map.once("vortex:ready", fillMap);

  init3D(active);
}

async function loadAdvisor() {
  const [state, priorities, access, reports] = await Promise.all([
    api.state(app.project), api.priorities(app.project), api.access(app.project), api.reports(app.project)]);
  app.state = state;
  app.priorities = priorities;
  app.access = access;
  renderReports(reports);
  refreshRoads();
}

function refreshRoads() {
  const fc = segmentsForVehicle(app.segments, app.state, app.vehicle);
  app.fc = fc;
  if (app.mapReady) setData(app.map, "segments", fc);
  renderRoads(fc, app.vehicle, openSegment);
  renderActNow(app.priorities, app.access, app.vehicle);
  app.three?.setRoads({ ...fc, features: fc.features.filter((f) => f.properties.measured) });
}

function openSegment(id) {
  const seg = app.fc?.features.find((f) => f.properties.segment_id === id);
  if (!seg) return;
  const st = app.state?.segments?.find((s) => s.segment_id === id);
  showTab("roads");
  renderSegmentDetail(seg, st);
  $("back-roads").addEventListener("click", () => renderRoads(app.fc, app.vehicle, openSegment));
}

function freshness(spec, active) {
  const surveyed = active.project.startsWith("southfork") ? "Surveyed 30 Apr 2024" : "Survey date unknown";
  return `${surveyed} · active since ${new Date(active.set_at).toLocaleString()}`;
}

function init3D(active) {
  const btn = $("toggle-3d");
  if (!active.terrain) {
    btn.disabled = true;
    btn.title = "No 3D terrain exported for this run yet";
    return;
  }
  btn.addEventListener("click", async () => {
    const on = btn.getAttribute("aria-pressed") !== "true";
    btn.setAttribute("aria-pressed", String(on));
    $("three").hidden = !on;
    $("map").hidden = on;
    $("exaggeration").hidden = !on;
    if (on && !app.three) {
      status("Loading 3D terrain…");
      const { createThreeView } = await import("./three-view.js");
      app.three = await createThreeView($("three"), active.terrain, active.terrain.url);
      app.three.setRoads({ ...app.fc, features: (app.fc?.features || []).filter((f) => f.properties.measured) });
      status("");
    }
    if (!on) app.map.resize();
  });
  $("exag").addEventListener("input", (e) => {
    $("exag-value").textContent = e.target.value;
    app.three?.setExaggeration(Number(e.target.value));
  });
}

boot();
