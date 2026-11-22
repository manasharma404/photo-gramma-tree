import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/space-grotesk/latin-400.css";
import "@fontsource/space-grotesk/latin-500.css";
import "./styles/tokens.css";
import "./styles/app.css";
import { SNAPSHOT, api, getJSON, postJSON } from "./api.js";
import { VEHICLES, chip, esc } from "./format.js";
import { ICONS, mountIcons } from "./icons.js";
import { LAYER_GROUPS, createMap, legendHTML, segmentsForVehicle, setData, setGroupVisible } from "./map.js";
import { accuracyMiniHTML, initTabs, renderAccuracy, renderActNow, renderMeasureIntro, renderMeasureResult, renderReports, renderRoads,
  renderSegmentDetail, showTab } from "./panel.js";
import { initTools } from "./tools.js";
import { initTour } from "./tour.js";
import { PASS_LABEL, addDemoLayers, planReflight, planRoute } from "./demo.js";

const $ = (id) => document.getElementById(id);
const app = { vehicle: "foot", segments: null, state: null, mapReady: false, demo: null, graphLog: [] };
window.__vortex = app; // inspection handle for the headless check (scripts/screenshot.mjs)

// Data labels (hard rule 6): public data is never presented as our footage; the demo always says it is simulated.
const DATA_LABEL = {
  southfork: "USGS public data · South Fork debris flow, California, 30 Apr 2024 · not our footage",
  wayanad: "Scenario reconstructed from reports · not drone-measured",
  neo2: "Our footage · DJI Neo 2",
  demo: "SIMULATED demo · real OpenStreetMap roads · damage and people made up",
};
const labelFor = (project) => Object.entries(DATA_LABEL).find(([k]) => project?.startsWith(k))?.[1] || "";
const vehicleLabel = () => VEHICLES.find(([k]) => k === app.vehicle)[1];
const status = (msg) => ($("statusline").textContent = msg || "");
const isDemo = () => app.project === "demo";

async function boot() {
  mountIcons();
  initTabs(() => $("panel").classList.add("expanded")); // phone: picking a section opens the sheet
  $("panel-head").addEventListener("click", () => $("panel").classList.toggle("expanded"));
  $("layers-btn").addEventListener("click", () => {
    const open = $("layers").classList.toggle("open");
    $("layers-btn").setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (e) => {
    const go = e.target.closest("[data-goto]");
    if (go) showTab(go.dataset.goto);
  });
  renderMeasureIntro();

  const [active, health, me, demo] = await Promise.all([api.active(), api.health(), SNAPSHOT ? null : getJSON("/auth/me"),
    SNAPSHOT ? null : getJSON("/advisor/demo/scenario")]);
  app.me = me;
  if (me?.auth && me.role) {  // who is signed in, and a way out
    const who = $("who");
    who.textContent = `${{ operator: "Operator", evaluator: "Evaluator", field: me.team || "Field team" }[me.role]} · Sign out`;
    who.hidden = false;
    who.addEventListener("click", async () => {
      await fetch("/auth/logout", { method: "POST" });
      location.replace("/login/");
    });
  }
  const off = $("offline");
  off.dataset.state = !health ? "down" : health.snapshot || !health.internet_reachable ? "offline" : "online";
  $("offline-text").textContent = !health ? "API not reachable"
    : health.snapshot ? `Read-only snapshot · ${new Date(health.captured_at).toLocaleDateString([], { day: "numeric", month: "short" })}`
    : health.internet_reachable ? "Online (not needed)" : "Offline mode";

  if (!active && !demo) {
    $("site").innerHTML = `<option>No map processed yet</option>`;
    $("tab-act").innerHTML = `<p class="empty">No map is active. Process a survey, then run <code>python -m pipeline.activate</code>.</p>`;
    return;
  }
  // Site: the demo scenario (default when it exists) or our real survey run.
  let pick = null;
  try { pick = localStorage.getItem("typhon-site"); } catch { /* private mode */ }
  const useDemo = demo && (pick === "demo" || !pick || !active);
  app.project = useDemo ? "demo" : active.project;
  app.demo = useDemo ? demo : null;
  document.body.classList.toggle("is-demo", !!useDemo);
  $("site").innerHTML = (demo ? `<option value="demo">Demo: landslide scenario (simulated)</option>` : "")
    + (active ? `<option value="survey">${esc(prettySite(active.project))} (real survey)</option>` : "");
  $("site").value = useDemo ? "demo" : "survey";
  $("site").addEventListener("change", () => {
    try { localStorage.setItem("typhon-site", $("site").value); } catch { /* ignore */ }
    location.reload();
  });
  $("dataset").textContent = labelFor(app.project);
  if (useDemo) $("freshness-field").hidden = true;
  else {
    $("dataset").title = `run ${active.run_id}`;
    $("freshness").textContent = new Date(active.set_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
  }

  $("vehicle").innerHTML = VEHICLES.map(([k, l]) => `<button role="radio" data-v="${k}" aria-checked="${k === app.vehicle}">${l}</button>`).join("");
  $("vehicle").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    app.vehicle = b.dataset.v;
    $("vehicle").querySelectorAll("button").forEach((x) => x.setAttribute("aria-checked", String(x === b)));
    refresh();
  }));

  // the map: our orthophoto only when the site is that survey (the demo has no imagery of its own)
  const sameBase = useDemo && active && demo.base === active.project;
  const mapActive = useDemo ? { ...(active || {}), tiles: sameBase ? active.tiles : null, image: null } : active;
  const map = createMap($("map"), mapActive, openSegment);
  app.map = map;
  if (!useDemo && !SNAPSHOT && health?.mounted_routers?.live) {  // the growing map: real survey sites only
    const startLive = () => import("./live.js").then(({ initLive }) => initLive(map, $("live")));
    if (map.loaded()) startLive(); else map.once("vortex:ready", startLive);
  }
  if (!useDemo) initTools(map, { onStatus: status, onResult: (m) => renderMeasureResult(m) });
  $("legend").innerHTML = legendHTML(useDemo);
  initLayers(mapActive);

  // Panels don't wait for the map to draw (a hidden or slow map must not leave them empty).
  if (useDemo) {
    app.segments = demo.segments;
    app.places = demo.places;
    app.spec = null;
    renderReports(null);
  } else {
    const [segments, places, checkpoints, spec] = await Promise.all([
      api.layer("segments"), api.layer("places"), api.layer("checkpoints"), api.spec()]);
    Object.assign(app, { segments, places, checkpoints, spec });
    renderAccuracy(spec);
  }
  renderOverview(active);
  renderStripRight();
  await loadAdvisor(useDemo ? "Opened the demo scenario" : "Opened the map");
  if (!SNAPSHOT) setTimeout(watchReports, 3000);
  initTour(() => app.spec);

  const fillMap = () => {
    app.mapReady = true;
    setData(map, "places", app.places);
    if (app.checkpoints) setData(map, "checkpoints", app.checkpoints);
    if (useDemo) {
      app.demoLayers = addDemoLayers(map, demo, { onBlockage: (b) => openSegment(b.segment_id), onPeople: (p) => showRouteTo(p) });
      const [w, s, e, n] = demo.bounds_wsen;
      map.fitBounds([[w, s], [e, n]], { padding: { top: 60, bottom: 60, left: 60, right: 260 }, duration: 0 });
    }
    refresh();
  };
  if (map.getSource("segments")) fillMap();
  else map.once("vortex:ready", fillMap);
}

function prettySite(p) {
  if (p.startsWith("southfork")) return `South Fork debris flow (${p.replace("southfork_", "").replace("_", "-").toUpperCase()})`;
  if (p.startsWith("wayanad")) return "Wayanad scenario";
  return p;
}

// ---- the route graph: every answer about access comes from it; the strip card shows it working ----
// Two engines answer the same question: NetworkX right away (under a second), so the map updates at once, and
// Neo4j in the background (several seconds on a big network). When Neo4j lands, its answer replaces the quick one
// and the panel says whether the two agree. A newer change supersedes an older Neo4j check.
const sameAnswer = (a, b) => JSON.stringify((a?.places || []).map((p) => [p.place_id, p.reachable]))
  === JSON.stringify((b?.places || []).map((p) => [p.place_id, p.reachable]));
async function loadAdvisor(trigger) {
  const seq = (app.seq = (app.seq || 0) + 1);
  renderGraph({ busy: true, trigger });
  const t0 = performance.now();
  const q = encodeURIComponent(app.project);
  const [state, priorities, access, reports] = await Promise.all([
    api.state(app.project), getJSON(`/advisor/priorities?project=${q}&backend=networkx`),
    getJSON(`/advisor/access?project=${q}&backend=networkx`), api.reports(app.project)]);
  Object.assign(app, { state, priorities, access });
  app.lastReportId = reports?.reports?.at(-1)?.id ?? app.lastReportId ?? 0;
  renderReports(reports);
  const entry = { trigger, seconds: access?.timing_s ?? (performance.now() - t0) / 1000, at: new Date(), neo: "checking", neoStart: performance.now() };
  app.graphLog.unshift(entry);
  app.graphLog = app.graphLog.slice(0, 4);
  renderGraph({});
  refresh();
  if (SNAPSHOT) { entry.neo = "unavailable"; renderGraph({}); return; }
  getJSON(`/advisor/access?project=${q}&backend=neo4j`).then((neo) => {
    if (seq !== app.seq) { entry.neo = "superseded"; return; }
    if (!neo) { entry.neo = "unavailable"; renderGraph({}); return; }
    entry.neo = sameAnswer(access, neo) ? "agrees" : "differs";
    entry.neoSeconds = neo.timing_s ?? (performance.now() - entry.neoStart) / 1000;
    app.access = neo;
    refresh();
  });
}

const ENGINE = (cw) => !cw ? "not available" : cw.startsWith("neo4j") ? "Neo4j graph database" : "NetworkX (Neo4j is not running)";
const cutPlaces = (v) => (app.access?.places || []).filter((p) => p.reachable?.[v] === false);
function peopleCut(v) {
  const cut = new Set(cutPlaces(v).map((p) => p.place_id));
  return (app.demo?.people || []).filter((p) => cut.has(p.place_id)).reduce((s, p) => s + p.count, 0);
}

function renderGraph({ busy = false, trigger = "" } = {}) {
  const el = $("graph-body");
  $("card-graph").classList.toggle("is-busy", busy);
  if (busy) {
    const t0 = performance.now();
    el.innerHTML = `<div class="graph__busy"><span class="pulse"></span><div><strong>Recomputing routes for 4 vehicles…</strong>
      <span class="muted">${esc(trigger)} · <span id="graph-tick">0.0</span> s</span></div></div>`;
    clearInterval(app._tick);
    app._tick = setInterval(() => { const t = $("graph-tick"); if (t) t.textContent = ((performance.now() - t0) / 1000).toFixed(1); }, 100);
    return;
  }
  clearInterval(app._tick);
  const a = app.access, last = app.graphLog[0];
  const checking = last?.neo === "checking";
  $("card-graph").classList.toggle("is-busy", checking);
  const rows = VEHICLES.map(([k, label]) => {
    const n = app.demo ? peopleCut(k) : cutPlaces(k).length;
    const total = app.demo ? app.demo.people_total : (a?.places || []).length;
    return `<div class="gbar"><span>${label}</span><i style="--w:${total ? Math.round((n / total) * 100) : 0}%"></i><b>${n}</b></div>`;
  }).join("");
  const neoLine = !last ? "" : last.neo === "checking"
      ? `<span class="pulse pulse--sm"></span>Neo4j is checking the same answer… <span id="graph-tick">0.0</span> s`
    : last.neo === "agrees" ? `<span class="ok">✓</span>Neo4j graph database: same answer, ${last.neoSeconds.toFixed(1)} s`
    : last.neo === "differs" ? `<span class="warn">!</span>Neo4j answered differently (${last.neoSeconds.toFixed(1)} s): showing Neo4j's answer`
    : "Neo4j is not running: the answer is from NetworkX";
  el.innerHTML = `<div class="graph__engine"><span class="dot dot--nx"></span>NetworkX answered in ${last ? last.seconds.toFixed(1) : "–"} s</div>
    <div class="graph__neo">${neoLine}</div>
    <div class="muted">${a?.graph_size ? `${a.graph_size.roads} roads · ${a.graph_size.places} places` : ""}</div>
    <div class="graph__head">${app.demo ? "People cut off (simulated)" : "Places cut off"}</div>${rows}
    <div class="graph__log">${app.graphLog.map((g) => `<div><span>${g.at.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</span>${esc(g.trigger)}${
      g.neo === "agrees" ? ` · Neo4j ✓ ${g.neoSeconds.toFixed(1)} s` : g.neo === "checking" ? " · Neo4j checking" : ""}</div>`).join("")}</div>`;
  if (checking) {
    app._tick = setInterval(() => { const t = $("graph-tick"); if (t) t.textContent = ((performance.now() - last.neoStart) / 1000).toFixed(1); }, 100);
  }
}

// Field reports arrive from phones on /field (or from the what-if buttons here). When a new one lands, re-run
// the advisor so roads recolour and the cut-off counts update, then say what changed. Live server only.
const KIND_TEXT = { dead_end: "blocked", new_debris: "new debris", cleared: "cleared", other: "note" };
async function watchReports() {
  const r = await api.reports(app.project);
  const latest = r?.reports?.at(-1);
  if (latest && latest.id > (app.lastReportId ?? 0) && !app.busy) {
    const before = app.demo ? peopleCut(app.vehicle) : cutPlaces(app.vehicle).length;
    app.lastReportId = latest.id;
    await loadAdvisor(`Field report: ${KIND_TEXT[latest.kind] || latest.kind} on ${latest.segment_id || latest.place_id || "a road"}`);
    const after = app.demo ? peopleCut(app.vehicle) : cutPlaces(app.vehicle).length;
    showReportToast(`Field report: ${KIND_TEXT[latest.kind] || latest.kind} on ${latest.segment_id || "a road"}`,
      `${app.demo ? "People" : "Places"} cut off for ${vehicleLabel().toLowerCase()}: ${before} → ${after}. Plan recomputed.`);
  }
  setTimeout(watchReports, 3000);
}

function showReportToast(title, body) {
  let el = document.getElementById("report-toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "report-toast";
    el.className = "report-toast";
    el.setAttribute("role", "status");
    document.body.append(el);
  }
  el.innerHTML = `<strong>${esc(title)}</strong><span>${esc(body)}</span>`;
  el.classList.remove("is-on");
  void el.offsetWidth;
  el.classList.add("is-on");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("is-on"), 9000);
}

function refresh() {
  const fc = segmentsForVehicle(app.segments, app.state, app.vehicle);
  app.fc = fc;
  if (app.mapReady) setData(app.map, "segments", fc);
  if (app.demo) {
    app.demoLayers?.recolour(app.access, app.vehicle);
    if (app.routeTarget) renderRoute(false);
    renderDemoAct();
    renderDemoRoads();
  } else {
    renderRoads(fc, vehicleLabel(), openSegment);
    renderActNow({ priorities: app.priorities, access: app.access, fc, spec: app.spec, vehicle: app.vehicle, vehicleLabel: vehicleLabel() });
  }
  if (app.access) renderGraph({ busy: false });
  renderStripRight();
}

// ---- demo panels ----
const flyTo = (lonlat, zoom = 16) => app.map?.flyTo({ center: lonlat, zoom, duration: 900 });
function renderDemoAct() {
  const d = app.demo, v = app.vehicle, a = app.access;
  const byId = Object.fromEntries((a?.places || []).map((p) => [p.place_id, p]));
  const cut = peopleCut(v), groups = d.people.filter((p) => byId[p.place_id]?.reachable?.[v] === false).length;
  const blockTitle = Object.fromEntries(d.blockages.map((b) => [b.segment_id, b]));
  const reopen = (a?.reopen_plan || []).filter((r) => !r.mode || r.mode === v).slice(0, 3);
  const zone = d.blur_zones[0];
  $("tab-act").innerHTML = `<div class="demo-note">${ICONS.alert}<span><b>Simulated demo.</b> Real roads (OpenStreetMap); the damage and the people are made up to show how Typhon decides.</span></div>`
    + `<div class="alert ${cut ? "" : "alert--ok"}">${ICONS.alert}<div><strong>${cut} people cut off for ${esc(vehicleLabel().toLowerCase())}</strong>
        <span>${groups} of ${d.people.length} groups have no road open to this vehicle. Pick another vehicle above to compare.</span></div></div>`
    + `<h2>Clear first</h2>` + (reopen.length ? reopen.map((r) => {
        const b = blockTitle[r.segment_id];
        return `<article class="item item--click" data-seg="${esc(r.segment_id)}"><h3>${r.rank}. ${esc(b ? b.title : `Clear ${r.segment_id}`)}</h3>
          <div class="muted">Reconnects <b>${r.reconnects_people ?? "?"}</b> people in ${r.reconnects_places ?? "?"} places${r.debris_volume_m3 != null ? ` · about ${Math.round(r.debris_volume_m3)} m³ of debris (simulated)` : ""}</div></article>`;
      }).join("") : `<p class="empty">${cut ? "No single road reopens a route for this vehicle: the groups cut off are behind more than one blockage, so clear them in order." : "Nothing to clear for this vehicle: every group it can serve is reachable."}</p>`)
    + `<h2>Roads that let only some through</h2>` + d.blockages.map((b) => `<article class="item item--click blk" data-seg="${esc(b.segment_id)}">
        <h3>${esc(b.title)}</h3><div class="passes">${Object.keys(PASS_LABEL).map((m) => `<span class="${b.passes.includes(m) ? "ok" : "no"}">${PASS_LABEL[m]}</span>`).join("")}</div></article>`).join("")
    + (zone ? `<h2>Fly next</h2><article class="item"><h3>Blurred photos: ${zone.segments.length} roads not seen</h3>
        <div class="muted">Until a clear pass, these roads are unknown, never shown as open.</div>
        <button class="btn-line" id="plan-refly">${ICONS.drone}Plan a re-fly of this patch</button></article>` : "")
    + `<h2>People (simulated)</h2>` + d.people.map((p) => {
        const r = byId[p.place_id]?.reachable?.[v];
        return `<div class="row people-row" data-pid="${esc(p.place_id)}" title="Show the route for this vehicle"><b class="ppl ppl--${r === false ? "cut" : r == null ? "unv" : "ok"}">${p.count}</b>
          <span>${esc(p.name)}</span><span class="muted">${r === false ? "cut off" : r == null ? "access unverified" : "reachable"}</span></div>`;
      }).join("");
  $("tab-act").querySelectorAll("[data-seg]").forEach((el) => el.addEventListener("click", () => {
    const b = d.blockages.find((x) => x.segment_id === el.dataset.seg);
    if (b) flyTo(b.lonlat);
    openSegment(el.dataset.seg);
  }));
  $("tab-act").querySelectorAll(".people-row").forEach((el) => el.addEventListener("click", () => showRouteTo(d.people.find((x) => x.place_id === el.dataset.pid))));
  $("plan-refly")?.addEventListener("click", () => showReflight(zone));
}

function renderDemoRoads() {
  const d = app.demo;
  const counts = {};
  (app.fc?.features || []).forEach((f) => (counts[f.properties.status] = (counts[f.properties.status] || 0) + 1));
  $("tab-roads").innerHTML = `<p class="muted">${(app.fc?.features || []).length} roads for <strong>${esc(vehicleLabel())}</strong> (simulated statuses)</p>
    <p>${Object.entries(counts).map(([s, n]) => `${chip(s)} ${n}`).join(" &nbsp; ")}</p>
    <p class="muted">Click any road on the map to report it blocked or cleared, and watch the route graph recompute.</p>`
    + d.blockages.map((b) => `<div class="row" data-seg="${esc(b.segment_id)}">${chip(b.passes.length ? "partial" : "blocked")}<span>${esc(b.title)}</span></div>`).join("");
  $("tab-roads").querySelectorAll("[data-seg]").forEach((r) => r.addEventListener("click", () => openSegment(r.dataset.seg)));
}

function showReflight(zone) {
  const plan = planReflight(zone);
  app.demoLayers?.showFlight(plan);
  const c = zone.polygon.coordinates[0];
  const lng = c.map((x) => x[0]), lat = c.map((x) => x[1]);
  app.map.fitBounds([[Math.min(...lng), Math.min(...lat)], [Math.max(...lng), Math.max(...lat)]], { padding: 140, duration: 900 });
  const el = $("refly");
  el.hidden = false;
  el.innerHTML = `<header><span>${ICONS.drone}Re-fly plan</span><button class="x" id="refly-close" aria-label="Close">${ICONS.close}</button></header>
    <div class="refly__nums"><div><b>${plan.lines}</b><span>passes</span></div><div><b>${(plan.length_m / 1000).toFixed(1)}</b><span>km</span></div>
      <div><b>${plan.minutes}</b><span>min</span></div><div><b>${plan.photos}</b><span>photos</span></div></div>
    <p class="muted"><b>Estimate</b> from stated settings: ${esc(plan.assumptions)}. Fly it, then the new photos replace the blurred ones.</p>`;
  $("refly-close").addEventListener("click", () => { el.hidden = true; app.demoLayers?.showFlight(null); });
}

// ---- the route for the chosen vehicle, from the base to a group of people (recomputed when the vehicle changes) ----
function showRouteTo(p) {
  if (!p) return;
  app.routeTarget = p;
  renderRoute(true);
}
function renderRoute(fit) {
  const d = app.demo, p = app.routeTarget, el = $("route");
  if (!d || !p || !app.fc) return;
  const baseF = (d.places?.features || []).find((f) => f.properties.place_id === d.base_place_id);
  const from = baseF?.geometry?.coordinates;
  const r = from ? planRoute(app.fc, from, p.lonlat) : null;
  const byId = Object.fromEntries((app.fc.features || []).map((f) => [f.properties.segment_id, f.geometry]));
  app.demoLayers?.showRoute(r, byId);
  const v = vehicleLabel().toLowerCase();
  const stById = Object.fromEntries((app.state?.segments || []).map((s) => [s.segment_id, s]));
  const why = (id) => {
    const b = d.blockages.find((x) => x.segment_id === id);
    if (b) return b.title;
    const reason = stById[id]?.reasons_by_mode?.[app.vehicle]?.[0] || "a blocked road";
    return reason.replace(/^.*?simulated( rule)?: /, "").replace(/^rule=[^:]*: /, "");
  };
  const needs = r ? [...new Set(r.blocked.map(why))] : [];
  const km = r ? (r.length_m / 1000).toFixed(1) : "-";
  let line;
  if (!r) line = "No road links the base to this group.";
  else if (r.kind === "ok") line = "<b>Open route, " + km + " km</b>" + (r.partial ? " · " + r.partial + (r.partial > 1 ? " stretches" : " stretch") + " passable with care" : "") + ".";
  else if (r.kind === "unverified") line = "<b>Only through roads not seen</b> (" + r.unknown + "), " + km + " km. Fly there first to confirm.";
  else line = "<b>Cut off for " + esc(v) + ".</b> Clear " + needs.slice(0, 2).map((x) => "<b>" + esc(x) + "</b>").join(" and ")
    + (needs.length > 2 ? " and " + (needs.length - 2) + " more" : "") + " to open a " + km + " km route.";
  el.hidden = false;
  el.innerHTML = '<header><span>' + ICONS.roads + 'Route for ' + esc(v) + '</span><button class="x" id="route-close" aria-label="Close">' + ICONS.close + '</button></header>'
    + '<p class="route__to">To <b>' + esc(p.name) + '</b> · ' + p.count + ' people (simulated)</p>'
    + '<p class="route__line route__line--' + (r ? r.kind : "none") + '">' + line + '</p>'
    + '<p class="muted">Switch the vehicle at the top to see how the route changes.</p>';
  $("route-close").addEventListener("click", () => { app.routeTarget = null; el.hidden = true; app.demoLayers?.showRoute(null); });
  if (fit && r) {
    const lng = r.coords.map((c) => c[0]), lat = r.coords.map((c) => c[1]);
    app.map.fitBounds([[Math.min(...lng), Math.min(...lat)], [Math.max(...lng), Math.max(...lat)]], { padding: { top: 150, bottom: 80, left: 80, right: 80 }, maxZoom: 16, duration: 900 });
  }
}

function openSegment(id) {
  const seg = app.fc?.features.find((f) => f.properties.segment_id === id);
  if (!seg) return;
  showTab("roads");
  renderSegmentDetail(seg, app.state?.segments?.find((s) => s.segment_id === id));
  if (app.demo) {
    $("tab-roads").insertAdjacentHTML("afterbegin", `<div class="whatif"><p class="muted">What if a field team reports this road? The route graph recomputes for all four vehicles.</p>
      <button class="btn-line" data-k="dead_end">Report blocked</button><button class="btn-line" data-k="cleared">Report cleared</button></div>`);
    $("tab-roads").querySelectorAll(".whatif button").forEach((b) => b.addEventListener("click", async () => {
      $("tab-roads").querySelectorAll(".whatif button").forEach((x) => (x.disabled = true));
      try {
        app.busy = true;
        const saved = await postJSON("/advisor/reports", { project: "demo", segment_id: id, kind: b.dataset.k,
          note: "what-if from the dashboard (demo)", reporter: "Dashboard what-if" });
        app.lastReportId = Math.max(app.lastReportId ?? 0, saved?.report?.id ?? saved?.id ?? 0);
        const before = peopleCut(app.vehicle);
        await loadAdvisor(`Road ${id} reported ${KIND_TEXT[b.dataset.k]}`);
        showReportToast(`Road ${id} reported ${KIND_TEXT[b.dataset.k]}`, `People cut off for ${vehicleLabel().toLowerCase()}: ${before} → ${peopleCut(app.vehicle)}. Recomputed in ${app.graphLog[0]?.seconds.toFixed(1)} s.`);
      } catch (e) {
        status(`Could not report: ${e.message}`);
      } finally {
        app.busy = false;
        openSegment(id);
      }
    }));
  }
  $("back-roads")?.addEventListener("click", () => (app.demo ? renderDemoRoads() : renderRoads(app.fc, vehicleLabel(), openSegment)));
}

function initLayers(active) {
  const groups = Object.entries(LAYER_GROUPS).filter(([k]) => (k !== "ortho" || active?.tiles) && (!app.demo || !["checkpoints", "results"].includes(k)));
  $("layer-list").innerHTML = groups.map(([k, g]) => `<label class="layer"><span>${g.label}</span>
      <span class="switch"><input type="checkbox" data-layer="${k}" checked><span></span></span></label>`).join("")
    + (app.demo ? `<label class="layer"><span>Simulated damage &amp; people</span><span class="switch"><input type="checkbox" data-layer="demo" checked><span></span></span></label>` : "");
  $("layer-list").querySelectorAll("input").forEach((i) => i.addEventListener("change", () => (i.dataset.layer === "demo"
    ? app.demoLayers?.setVisible(i.checked) : setGroupVisible(app.map, i.dataset.layer, i.checked))));
}

function renderOverview(active) {
  const canReset = app.demo && app.me?.role !== "evaluator" && app.me?.role !== "field";
  $("card-overview").innerHTML = app.demo
    ? `<header><span>Overview</span></header><div class="label-public">Simulated demo</div>
       <div class="muted">Real roads from OpenStreetMap. Blockages, the blurred patch and the people are made up, to show what Typhon decides on a day like this.</div>
       ${canReset ? `<button class="btn-line btn-line--sm" id="demo-reset">Reset demo</button>` : ""}`
    : `<header><span>Overview</span></header><div class="label-public">${esc(labelFor(active.project))}</div>
       <div class="muted">${esc(prettySite(active.project))}. Mapped from drone images without ground control; every number on screen comes from a run on this laptop.</div>`;
  $("demo-reset")?.addEventListener("click", async () => {
    try { await postJSON("/advisor/demo/reset", {}); await loadAdvisor("Demo reset to the start"); }
    catch (e) { status(`Could not reset: ${e.message}`); }
  });
  // the 3D terrain is kept as a picture only (it was not adding to decisions)
  if (active?.terrain) {
    $("thumb-3d").style.backgroundImage = `url(${active.terrain.url}${active.terrain.thumb || active.terrain.texture.file})`;
    if (app.demo) $("card-3d").querySelector("header span").textContent = "3D terrain · from our survey run";
  } else $("card-3d").hidden = true;
}

function renderStripRight() {
  const card = $("card-accuracy");
  if (app.demo) {
    const total = app.demo.people_total, cut = peopleCut(app.vehicle);
    card.innerHTML = `<header><span>People (simulated)</span></header><div class="big">${cut} <small>of ${total}</small></div>
      <div class="muted">cut off for ${esc(vehicleLabel().toLowerCase())}, in ${app.demo.people.length} groups</div>`;
  } else if (app.spec?.accuracy) {
    card.innerHTML = `<header><span>Accuracy</span></header><div id="accuracy-mini">${accuracyMiniHTML(app.spec)}</div>`;
  } else card.hidden = true;
}

boot();
