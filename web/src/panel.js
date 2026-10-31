// Side panel tabs. Content follows docs/ui_layout_brief.md section 2C; styling is the lead's.
import { NOT_MEASURED, VEHICLES, chip, esc, num, withTol } from "./format.js";

const $ = (id) => document.getElementById(id);

export function initTabs() {
  document.querySelectorAll(".tabs [data-tab]").forEach((b) =>
    b.addEventListener("click", () => showTab(b.dataset.tab)));
}

export function showTab(name) {
  document.querySelectorAll(".tabs [data-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === name)));
  document.querySelectorAll(".tabpanel").forEach((p) => (p.hidden = p.id !== `tab-${name}`));
}

export function renderActNow(priorities, access, vehicle) {
  const el = $("tab-act");
  const items = priorities?.items || [];
  const reopen = (access?.reopen_plan || []).filter((r) => !r.mode || r.mode === vehicle);
  if (!items.length && !reopen.length) {
    el.innerHTML = `<p class="empty">No priorities yet: they need road and place data for this site.</p>`;
    return;
  }
  el.innerHTML = `<p class="muted">Decision support: ranked by hand-set weights (PLACEHOLDER), not an automated dispatch.</p>`
    + items.map((it) => `<article class="card">
        <h3>${it.rank}. ${esc(it.recommended_action)}</h3>
        <div class="muted">${esc(it.target_kind)} ${esc(it.target_id)} · ${esc(it.level)}${it.score != null ? ` · score ${num(it.score, "", 0)}` : ""}</div>
        <ul>${(it.reasons || []).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        ${it.needs_verification ? `<span class="chip">needs verification</span>` : ""}
        ${it.unknown_factors?.length ? `<div class="muted">Unknown: ${it.unknown_factors.map(esc).join(", ")}</div>` : ""}
      </article>`).join("")
    + (reopen.length ? `<h3>Reopen plan (${esc(vehicle)})</h3>` + reopen.map((r) => `<article class="card">
        <h3>${r.rank}. Clear ${esc(r.segment_id)}</h3>
        <dl class="kv"><dt>Reconnects people</dt><dd>${num(r.reconnects_people, "", 0)}</dd>
        <dt>Reconnects places</dt><dd>${num(r.reconnects_places, "", 0)}</dd>
        <dt>Debris</dt><dd>${num(r.debris_volume_m3, "m³")}</dd></dl>
        <ul>${(r.reasons || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul></article>`).join("") : "");
}

export function renderRoads(segments, vehicle, onPick) {
  const el = $("tab-roads");
  const feats = (segments?.features || []).filter((f) => f.properties.measured);
  if (!feats.length) {
    el.innerHTML = `<p class="empty">No measured road segments for this site yet.</p>`;
    return;
  }
  const counts = {};
  feats.forEach((f) => (counts[f.properties.status] = (counts[f.properties.status] || 0) + 1));
  el.innerHTML = `<p class="muted">${feats.length} measured segments for <strong>${esc(vehicle)}</strong>: `
    + Object.entries(counts).map(([s, n]) => `${chip(s)} ${n}`).join(" ") + `</p>`
    + feats.map((f) => `<div class="row" data-seg="${esc(f.properties.segment_id)}">${chip(f.properties.status)}
        ${esc(f.properties.segment_id)} · ${esc(f.properties.highway)} · ${num(f.properties.length_m, "m", 0)}
        ${f.properties.needs_verification ? `<span class="chip">verify</span>` : ""}</div>`).join("");
  el.querySelectorAll("[data-seg]").forEach((r) => r.addEventListener("click", () => onPick(r.dataset.seg)));
}

export function renderSegmentDetail(seg, stateEntry) {
  const el = $("tab-roads");
  const p = seg.properties;
  el.innerHTML = `<button id="back-roads">← All segments</button>
    <article class="card"><h3>${esc(p.segment_id)} · ${esc(p.highway)}</h3>
    <dl class="kv">
      <dt>Length</dt><dd>${num(p.length_m, "m")}</dd>
      <dt>Corridor width</dt><dd>${num(p.corridor_width_m, "m")} <span class="muted">(${esc(p.corridor_width_source)})</span></dd>
      <dt>Coverage</dt><dd>${p.coverage_fraction == null ? NOT_MEASURED : Math.round(p.coverage_fraction * 100) + " %"}</dd>
      <dt>Clear width</dt><dd>${num(p.min_clear_width_m, "m", 2)}</dd>
      <dt>Max obstruction</dt><dd>${num(p.max_obstruction_m, "m", 2)}</dd>
      <dt>Obstructed length</dt><dd>${num(p.obstructed_length_m, "m")}</dd>
      <dt>Debris volume</dt><dd>${withTol(p.debris_volume_m3, p.debris_volume_tolerance_m3, "m³")}</dd>
    </dl></article>
    <article class="card"><h3>Status by vehicle</h3>${VEHICLES.map(([k, label]) => `
      <div>${chip(stateEntry?.status_by_mode?.[k] || "unknown")} <strong>${label}</strong>
      <ul>${(stateEntry?.reasons_by_mode?.[k] || ["no assessment yet"]).map((r) => `<li class="muted">${esc(r)}</li>`).join("")}</ul></div>`).join("")}
      <div class="muted">Source: ${esc(stateEntry?.source || "—")}${stateEntry?.needs_verification ? " · needs verification" : ""}</div>
    </article>`;
}

export function renderAccuracy(spec) {
  const el = $("tab-accuracy");
  const a = spec?.accuracy, t = spec?.timing, l = spec?.laptop;
  el.innerHTML = `<article class="card"><h3>Positional accuracy</h3>${a ? `<dl class="kv">
      <dt>Horizontal</dt><dd>± ${num(a.horizontal.rmse_h_m, "m", 2)} RMSE</dd>
      <dt>Vertical</dt><dd>${a.vertical.rmse_v_m == null ? NOT_MEASURED : "± " + num(a.vertical.rmse_v_m, "m", 2) + " RMSE"}</dd>
      <dt>Checkpoints</dt><dd>${a.n_checkpoints} (${esc(a.checkpoint_method)})</dd>
      <dt>Ground control used</dt><dd>${a.used_gcps ? "yes" : "no"}</dd></dl>
      <p class="muted">${esc(a.standard_note)}</p>${a.datum_note ? `<p class="muted">${esc(a.datum_note)}</p>` : ""}` : NOT_MEASURED}</article>
    <article class="card"><h3>Processing</h3><dl class="kv">
      <dt>Area</dt><dd>${num(t?.area_ha, "ha", 2)}</dd><dt>Time</dt><dd>${num(t?.total_minutes, "min")}</dd>
      <dt>Per hectare</dt><dd>${num(t?.minutes_per_ha, "min/ha", 2)}</dd><dt>Tier</dt><dd>${esc(t?.tier || "—")}</dd></dl></article>
    <article class="card"><h3>Laptop</h3>${l ? `<dl class="kv"><dt>CPU</dt><dd>${esc(l.cpu?.model)}</dd>
      <dt>RAM</dt><dd>${num(l.ram_gb_visible_to_windows, "GB")}</dd><dt>GPU</dt><dd>${esc(l.gpu?.model)}</dd></dl>` : NOT_MEASURED}</article>
    <article class="card"><h3>Tool vs tape</h3><p class="not-measured">PENDING: needs our own field measurements</p></article>
    <p class="muted">${(spec?.data_sources || []).map(esc).join(" · ")}</p>`;
}

export function renderReports(reports) {
  const el = $("tab-reports");
  const list = Array.isArray(reports) ? reports : reports?.reports || [];
  el.innerHTML = list.length ? list.map((r) => `<div class="row"><strong>${esc(r.kind)}</strong> · ${esc(r.segment_id || r.place_id || "")}
      <div class="muted">${esc(r.reported_at || r.created_at || "")} ${esc(r.note || "")}</div></div>`).join("")
    : `<p class="empty">No field reports yet. Phones can send them from /field.</p>`;
}

export function renderMeasureResult(m) {
  const el = $("tab-measure");
  const r = m.result;
  let body = "";
  if (m.type === "span") {
    body = `<dl class="kv"><dt>Span</dt><dd>${withTol(r.span_m, m.tolerance.value, "m", 2)}</dd>
      <dt>Bank A / B</dt><dd>${num(r.bank_a_height_m, "m")} / ${num(r.bank_b_height_m, "m")}</dd>
      <dt>Bed</dt><dd>${num(r.bed_elevation_m, "m")}</dd><dt>Panels</dt><dd>${r.panel_estimate?.count ?? NOT_MEASURED} <span class="muted">(PLACEHOLDER rule)</span></dd></dl>
      ${r.note ? `<p class="muted">${esc(r.note)}</p>` : ""}`;
  } else if (m.type === "volume") {
    body = `<dl class="kv"><dt>Volume</dt><dd>${withTol(r.volume_m3, m.tolerance.value, "m³")}</dd>
      <dt>Area</dt><dd>${num(r.area_m2, "m²")}</dd><dt>Max height</dt><dd>${num(r.max_height_m, "m", 2)}</dd></dl>
      <p class="muted">${esc(r.reference_surface)}</p>`;
  } else if (m.type === "working_space") {
    body = `<dl class="kv"><dt>Clear area</dt><dd>${num(r.width_m, "m")} × ${num(r.length_m, "m")}</dd>
      <dt>Needed</dt><dd>${r.requirement_m.width} × ${r.requirement_m.length} m (PLACEHOLDER)</dd>
      <dt>Meets it</dt><dd>${r.meets_requirement ? "yes" : "no"}</dd></dl>`;
  } else if (m.type === "landing_zones") {
    body = `<p>${esc(r.helicopter_label)} · FATO ≥ ${num(r.fato_required_m, "m")}</p>` + (r.candidates.length
      ? r.candidates.map((c, i) => `<div class="row">#${i + 1} · ${num(c.fato_side_m, "m")} square · slope ≤ ${num(c.max_slope_deg, "°")}
          <div class="muted">clear approaches: ${c.approach_dirs_clear.join(", ") || "none"}${c.approach_beyond_map ? " · approach runs beyond our map: check on the ground" : ""}</div></div>`).join("")
      : `<p class="empty">No candidate met every rule in the mapped area.</p>`);
  }
  el.insertAdjacentHTML("afterbegin", `<article class="card"><h3>${esc(m.type.replace("_", " "))}</h3>${body}
    ${m.placeholders_used?.length ? `<p class="muted">Placeholders: ${m.placeholders_used.map(esc).join(", ")}</p>` : ""}
    <p class="muted">Tolerance: ${esc(m.tolerance.method)}</p></article>`);
}

export function renderMeasureIntro() {
  $("tab-measure").innerHTML = `<p class="muted">Pick a tool on the map: Span (line across a gap), Volume (polygon around debris),
    Work area (click a point), Landing (search the map). Double-click to finish a line or polygon.</p>`;
}
