// Side panel content. Every number shown comes from the API; missing values say "not measured yet".
import { ICONS } from "./icons.js";
import { NOT_MEASURED, VEHICLES, chip, esc, num, withTol } from "./format.js";

const $ = (id) => document.getElementById(id);
const TITLES = {
  act: ["Act now", "What needs attention first, and why."],
  roads: ["Roads", "Measured segments and their status for the selected vehicle."],
  measure: ["Measure", "Span, debris volume, working space and landing zones from the height model."],
  accuracy: ["Accuracy & spec", "How far our map is from surveyed ground truth, and what it took."],
  reports: ["Field reports", "What teams on the ground have reported from /field."],
};

export function initTabs(onChange) {
  document.querySelectorAll("[role=tab][data-tab]").forEach((b) => b.addEventListener("click", () => { showTab(b.dataset.tab); onChange?.(b.dataset.tab); }));
}

export function showTab(name) {
  document.querySelectorAll("[role=tab][data-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".tabpanel").forEach((p) => (p.hidden = p.id !== `tab-${name}`));
  $("panel-title").textContent = TITLES[name][0];
  $("panel-sub").textContent = TITLES[name][1];
}

const insight = (icon, label, value, target = "") =>
  `<button class="insight" ${target ? `data-goto="${target}"` : ""}><span class="insight__icon">${ICONS[icon]}</span>
     <span><span class="insight__label">${label}</span><div class="insight__value">${value}</div></span>${target ? ICONS.chevron : "<span></span>"}</button>`;

export function renderActNow(ctx) {
  const { priorities, access, fc, spec, vehicle, vehicleLabel } = ctx;
  const el = $("tab-act");
  const measured = (fc?.features || []).filter((f) => f.properties.measured);
  const blocked = measured.filter((f) => f.properties.status === "blocked");
  const unknown = measured.filter((f) => f.properties.status === "unknown");
  const lenKm = (fs) => fs.reduce((s, f) => s + (f.properties.length_m || 0), 0) / 1000;
  const places = access?.places || [];
  const cut = places.filter((p) => p.reachable?.[vehicle] === false);
  const critical = (priorities?.items || []).filter((i) => i.level === "critical");
  const acc = spec?.accuracy;

  el.innerHTML = (critical.length ? `<div class="alert">${ICONS.alert}<div><strong>${critical.length} critical ${critical.length === 1 ? "place" : "places"}</strong>
      <span>Ranked by decision-support rules; see the list below.</span></div></div>` : "")
    + insight("roads", `Blocked for ${esc(vehicleLabel)}`, measured.length
      ? `${blocked.length} <small>of ${measured.length} measured segments · ${lenKm(blocked).toFixed(2)} km</small>` : NOT_MEASURED, "roads")
    + insight("act", `Places cut off for ${esc(vehicleLabel)}`, places.length ? `${cut.length} <small>of ${places.length}</small>` : NOT_MEASURED)
    + insight("layers", "Road we couldn't see (canopy, no data)", measured.length
      ? `${Math.round((unknown.length / measured.length) * 100)}% <small>of measured segments</small>` : NOT_MEASURED, "roads")
    + insight("accuracy", "Map accuracy", acc ? `± ${num(acc.horizontal.rmse_h_m, "m", 1)} <small>at ${acc.n_checkpoints} checkpoints</small>` : NOT_MEASURED, "accuracy")
    + `<h2>Priorities</h2><p class="muted">Decision support with hand-set weights (PLACEHOLDER), not an automated dispatch.</p>`
    + ((priorities?.items || []).map((it) => `<article class="item">
        <h3>${it.rank}. ${esc(it.recommended_action)}</h3>
        <div class="muted">${esc(it.target_kind)} ${esc(it.target_id)} · ${esc(it.level)}${it.score != null ? ` · score ${num(it.score, "", 0)}` : ""}</div>
        <ul>${(it.reasons || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        ${it.needs_verification ? `<span class="chip chip--verify">needs verification</span>` : ""}</article>`).join("")
      || `<p class="empty">No priorities yet: they need road and place data for this site.</p>`)
    + reopenHTML(access, vehicle);
}

function reopenHTML(access, vehicle) {
  const reopen = (access?.reopen_plan || []).filter((r) => !r.mode || r.mode === vehicle);
  if (!reopen.length) return "";
  return `<h2>Reopen plan</h2>` + reopen.map((r) => `<article class="item"><h3>${r.rank}. Clear ${esc(r.segment_id)}</h3>
      <dl class="kv"><dt>Reconnects people</dt><dd>${num(r.reconnects_people, "", 0)}</dd>
      <dt>Reconnects places</dt><dd>${num(r.reconnects_places, "", 0)}</dd><dt>Debris</dt><dd>${num(r.debris_volume_m3, "m³")}</dd></dl>
      <ul>${(r.reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></article>`).join("");
}

export function renderRoads(fc, vehicleLabel, onPick) {
  const el = $("tab-roads");
  const feats = (fc?.features || []).filter((f) => f.properties.measured);
  if (!feats.length) { el.innerHTML = `<p class="empty">No measured road segments for this site yet.</p>`; return; }
  const counts = {};
  feats.forEach((f) => (counts[f.properties.status] = (counts[f.properties.status] || 0) + 1));
  el.innerHTML = `<p class="muted">${feats.length} measured segments for <strong>${esc(vehicleLabel)}</strong></p>
    <p>${Object.entries(counts).map(([s, n]) => `${chip(s)} ${n}`).join(" &nbsp; ")}</p>`
    + feats.map((f) => `<div class="row" data-seg="${esc(f.properties.segment_id)}">${chip(f.properties.status)}
        <span>${esc(f.properties.segment_id)} · ${esc(f.properties.highway)} · ${num(f.properties.length_m, "m", 0)}</span>
        ${f.properties.needs_verification ? `<span class="chip chip--verify">verify</span>` : ""}</div>`).join("");
  el.querySelectorAll("[data-seg]").forEach((r) => r.addEventListener("click", () => onPick(r.dataset.seg)));
}

export function renderSegmentDetail(seg, st) {
  const p = seg.properties;
  $("tab-roads").innerHTML = `<button class="back" id="back-roads">← All segments</button>
    <article class="item"><h3>${esc(p.segment_id)} · ${esc(p.highway)}</h3><dl class="kv">
      <dt>Length</dt><dd>${num(p.length_m, "m")}</dd>
      <dt>Corridor width</dt><dd>${num(p.corridor_width_m, "m")}<div class="muted">${esc(p.corridor_width_source)}</div></dd>
      <dt>Visible</dt><dd>${p.coverage_fraction == null ? NOT_MEASURED : Math.round(p.coverage_fraction * 100) + " %"}</dd>
      <dt>Clear width</dt><dd>${num(p.min_clear_width_m, "m", 2)}</dd>
      <dt>Max obstruction</dt><dd>${num(p.max_obstruction_m, "m", 2)}</dd>
      <dt>Obstructed</dt><dd>${num(p.obstructed_length_m, "m")}</dd>
      <dt>Debris</dt><dd>${withTol(p.debris_volume_m3, p.debris_volume_tolerance_m3, "m³")}</dd></dl></article>
    <h2>Status by vehicle</h2>${VEHICLES.map(([k, label]) => `<article class="item">
      <h3>${chip(st?.status_by_mode?.[k] || "unknown")} ${label}</h3>
      <ul>${(st?.reasons_by_mode?.[k] || ["no assessment yet"]).map((r) => `<li>${esc(r)}</li>`).join("")}</ul></article>`).join("")}
    <p class="muted">Source: ${esc(st?.source || "—")}${st?.needs_verification ? " · needs verification" : ""}</p>`;
}

export function renderAccuracy(spec) {
  const a = spec?.accuracy, t = spec?.timing, l = spec?.laptop;
  $("tab-accuracy").innerHTML = `<article class="item"><h3>Positional accuracy</h3>${a ? `<dl class="kv">
      <dt>Horizontal</dt><dd>± ${num(a.horizontal.rmse_h_m, "m", 2)} RMSE</dd>
      <dt>Vertical</dt><dd>${a.vertical.rmse_v_m == null ? NOT_MEASURED : "± " + num(a.vertical.rmse_v_m, "m", 2) + " RMSE"}</dd>
      <dt>Checkpoints</dt><dd>${a.n_checkpoints} (${esc(a.checkpoint_method)})</dd>
      <dt>Ground control</dt><dd>${a.used_gcps ? "used" : "not used"}</dd></dl>
      <p class="muted">${esc(a.standard_note)}</p>${a.datum_note ? `<p class="muted">${esc(a.datum_note)}</p>` : ""}` : `<p>${NOT_MEASURED}</p>`}</article>
    <article class="item"><h3>Processing</h3><dl class="kv">
      <dt>Area</dt><dd>${num(t?.area_ha, "ha", 2)}</dd><dt>Time</dt><dd>${num(t?.total_minutes, "min")}</dd>
      <dt>Per hectare</dt><dd>${num(t?.minutes_per_ha, "min/ha", 2)}</dd><dt>Tier</dt><dd>${esc(t?.tier || "—")}</dd></dl></article>
    <article class="item"><h3>Laptop</h3>${l ? `<dl class="kv"><dt>CPU</dt><dd>${esc(l.cpu?.model)}</dd>
      <dt>RAM</dt><dd>${num(l.ram_gb_visible_to_windows, "GB")}</dd><dt>GPU</dt><dd>${esc(l.gpu?.model)}</dd></dl>` : `<p>${NOT_MEASURED}</p>`}</article>
    <article class="item"><h3>Tool vs tape</h3><p class="not-measured">PENDING: needs our own field measurements</p></article>
    <p class="muted">${(spec?.data_sources || []).map(esc).join(" · ")}</p>`;
}

export function accuracyMiniHTML(spec) {
  const a = spec?.accuracy, t = spec?.timing;
  return a ? `<div class="big">± ${num(a.horizontal.rmse_h_m, "m", 1)}</div><div class="muted">horizontal RMSE at ${a.n_checkpoints} checkpoints · no ground control</div>
      <div class="muted">${t?.minutes_per_ha != null ? num(t.minutes_per_ha, "min/ha", 1) + " on this laptop" : ""}</div>`
    : `<div class="not-measured">not measured yet</div>`;
}

export function renderReports(reports) {
  const list = Array.isArray(reports) ? reports : reports?.reports || [];
  $("tab-reports").innerHTML = list.length ? list.map((r) => `<div class="row"><strong>${esc(r.kind)}</strong>
      <span>${esc(r.segment_id || r.place_id || "")}</span><span class="muted">${esc(r.reported_at || r.created_at || "")} ${esc(r.note || "")}</span></div>`).join("")
    : `<p class="empty">No field reports yet. Teams can send them from a phone at <strong>/field</strong>.</p>`;
}

export function renderMeasureIntro() {
  $("tab-measure").innerHTML = `<p class="muted">Pick a tool on the right of the map. Span: a line across a gap. Volume: a polygon around debris.
    Work area: one click. Landing: searches the whole map. Double-click finishes a line or polygon.</p><div id="measure-results"></div>`;
}

export function renderMeasureResult(m) {
  const r = m.result;
  let body = "";
  if (m.type === "span") {
    body = `<dl class="kv"><dt>Span</dt><dd>${withTol(r.span_m, m.tolerance.value, "m", 2)}</dd>
      <dt>Bank A / B</dt><dd>${num(r.bank_a_height_m, "m")} / ${num(r.bank_b_height_m, "m")}</dd>
      <dt>Bed</dt><dd>${num(r.bed_elevation_m, "m")}</dd><dt>Bailey panels</dt><dd>${r.panel_estimate?.count ?? NOT_MEASURED} <span class="muted">(PLACEHOLDER rule)</span></dd></dl>
      ${r.note ? `<p class="muted">${esc(r.note)}</p>` : ""}`;
  } else if (m.type === "volume") {
    body = `<dl class="kv"><dt>Volume</dt><dd>${withTol(r.volume_m3, m.tolerance.value, "m³")}</dd>
      <dt>Area</dt><dd>${num(r.area_m2, "m²")}</dd><dt>Max height</dt><dd>${num(r.max_height_m, "m", 2)}</dd></dl><p class="muted">${esc(r.reference_surface)}</p>`;
  } else if (m.type === "working_space") {
    body = `<dl class="kv"><dt>Clear area</dt><dd>${num(r.width_m, "m")} × ${num(r.length_m, "m")}</dd>
      <dt>Needed</dt><dd>${r.requirement_m.width} × ${r.requirement_m.length} m <span class="muted">(PLACEHOLDER)</span></dd>
      <dt>Meets it</dt><dd>${r.meets_requirement ? "yes" : "no"}</dd></dl>`;
  } else if (m.type === "landing_zones") {
    body = `<p class="muted">${esc(r.helicopter_label)} · FATO ≥ ${num(r.fato_required_m, "m")}</p>` + (r.candidates.length
      ? r.candidates.map((c, i) => `<div class="row">#${i + 1} · ${num(c.fato_side_m, "m")} square · slope ≤ ${num(c.max_slope_deg, "°")}
          <span class="muted">clear approaches: ${c.approach_dirs_clear.join(", ") || "none"}${c.approach_beyond_map ? " · approach runs beyond our map" : ""}</span></div>`).join("")
      : `<p class="empty">No candidate met every rule in the mapped area.</p>`);
  }
  $("measure-results").insertAdjacentHTML("afterbegin", `<article class="item"><h3>${esc(m.type.replace("_", " "))}</h3>${body}
    ${m.placeholders_used?.length ? `<p class="muted">Placeholders: ${m.placeholders_used.map(esc).join(", ")}</p>` : ""}
    <p class="muted">Tolerance: ${esc(m.tolerance.method)}</p></article>`);
}
