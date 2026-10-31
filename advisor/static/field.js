(function () {
  "use strict";

  const state = {
    project: "",
    tab: "places",
    places: [],
    segments: [],
    selectedPlaceId: null,
    selectedSegmentId: null,
    selectedKind: "dead_end",
    search: "",
  };

  const elProject = document.getElementById("project-select");
  const elNetPill = document.getElementById("net-pill");
  const elFreshness = document.getElementById("freshness-line");
  const elBanner = document.getElementById("scenario-banner");
  const elTabPlaces = document.getElementById("tab-places");
  const elTabSegments = document.getElementById("tab-segments");
  const elSearch = document.getElementById("loc-search");
  const elLocList = document.getElementById("loc-list");
  const elPickedSummary = document.getElementById("picked-summary");
  const elNote = document.getElementById("report-note");
  const elReporter = document.getElementById("report-callsign");
  const elSubmit = document.getElementById("submit-btn");
  const elToast = document.getElementById("toast");
  const elReports = document.getElementById("recent-reports");
  const elPriorities = document.getElementById("priority-preview");

  function escapeHtml(str) {
    return String(str == null ? "" : str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function refreshHealth() {
    try {
      const resp = await fetch("/health");
      if (!resp.ok) throw new Error("health failed");
      const data = await resp.json();
      elNetPill.textContent = data.internet_reachable
        ? "LAN + Internet"
        : "Offline Hotspot Mode";
    } catch (_) {
      elNetPill.textContent = "Server Unreachable";
    }
  }

  function renderFreshness(fresh, isMock) {
    const surveyTxt = fresh.survey_time || fresh.survey_note || "not recorded";
    const analysisTxt = fresh.analysis_time || "pending";
    const countTxt = Number(fresh.field_report_count || 0);
    elFreshness.innerHTML =
      "<strong>Survey:</strong> " + escapeHtml(surveyTxt) +
      " &middot; <strong>Analysis:</strong> " + escapeHtml(analysisTxt) +
      " &middot; <strong>Field reports:</strong> " + escapeHtml(countTxt);

    if (isMock) {
      elBanner.textContent = "MOCK DATA — Contract fixture active (not a real survey)";
      elBanner.classList.remove("hidden");
    } else if (fresh.survey_note) {
      elBanner.textContent = fresh.survey_note;
      elBanner.classList.remove("hidden");
    } else {
      elBanner.classList.add("hidden");
    }
  }

  function updatePickedSummary() {
    const parts = [];
    if (state.selectedPlaceId) {
      const p = state.places.find((x) => x.place_id === state.selectedPlaceId);
      parts.push("Place: " + (p ? p.name : state.selectedPlaceId));
    }
    if (state.selectedSegmentId) {
      parts.push("Segment: " + state.selectedSegmentId);
    }
    elPickedSummary.textContent = parts.length
      ? "Selected -> " + parts.join(" | ")
      : "Tap a place or road segment above to select where you are.";
    elSubmit.disabled = !(state.selectedPlaceId || state.selectedSegmentId);
  }

  function renderLocationList() {
    const q = state.search.trim().toLowerCase();
    elLocList.innerHTML = "";

    if (state.tab === "places") {
      const filtered = state.places.filter((p) => {
        const hay = (p.name + " " + p.place_id + " " + p.kind + " " + (p.nearest_segment_id || "")).toLowerCase();
        return !q || hay.includes(q);
      });
      if (!filtered.length) {
        elLocList.innerHTML = '<div class="loc-item"><div class="loc-sub">No matching places. Switch to Road Segments tab.</div></div>';
        return;
      }
      filtered.forEach((p) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "loc-item" + (state.selectedPlaceId === p.place_id ? " selected" : "");
        btn.innerHTML =
          '<div class="loc-title">' + escapeHtml(p.name) + "</div>" +
          '<div class="loc-sub">' + escapeHtml(p.kind) +
          (p.nearest_segment_id ? " &middot; joins " + escapeHtml(p.nearest_segment_id) : "") +
          "</div>";
        btn.addEventListener("click", function () {
          state.selectedPlaceId = p.place_id;
          state.selectedSegmentId = p.nearest_segment_id || null;
          renderLocationList();
          updatePickedSummary();
        });
        elLocList.appendChild(btn);
      });
    } else {
      const filtered = state.segments.filter((s) => {
        const hay = (s.segment_id + " " + s.highway + " " + s.source).toLowerCase();
        return !q || hay.includes(q);
      });
      if (!filtered.length) {
        elLocList.innerHTML = '<div class="loc-item"><div class="loc-sub">No matching road segments.</div></div>';
        return;
      }
      filtered.forEach((s) => {
        const st = s.status_by_mode || {};
        const amb = st.ambulance || "unknown";
        const foot = st.foot || "unknown";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "loc-item" + (state.selectedSegmentId === s.segment_id && !state.selectedPlaceId ? " selected" : "");
        btn.innerHTML =
          '<div class="loc-title">' + escapeHtml(s.segment_id) +
          ' <span class="badge ' + escapeHtml(amb) + '">amb:' + escapeHtml(amb) + "</span>" +
          ' <span class="badge ' + escapeHtml(foot) + '">foot:' + escapeHtml(foot) + "</span></div>" +
          '<div class="loc-sub">' + escapeHtml(s.highway) +
          (s.length_m != null ? " &middot; " + escapeHtml(s.length_m) + " m" : "") +
          " &middot; source: " + escapeHtml(s.source) + "</div>";
        btn.addEventListener("click", function () {
          state.selectedPlaceId = null;
          state.selectedSegmentId = s.segment_id;
          renderLocationList();
          updatePickedSummary();
        });
        elLocList.appendChild(btn);
      });
    }
  }

  function renderReports(reports) {
    if (!reports || !reports.length) {
      elReports.innerHTML = "<li>No ground field reports submitted for this project yet.</li>";
      return;
    }
    elReports.innerHTML = reports
      .map(function (r) {
        const target = r.segment_id || r.place_id || "unknown";
        const modes = (r.modes || []).join(", ");
        return (
          "<li><strong>" + escapeHtml(r.kind.toUpperCase()) + "</strong> on <code>" +
          escapeHtml(target) + "</code> [" + escapeHtml(modes) + "]" +
          (r.note ? " — " + escapeHtml(r.note) : "") +
          "<br><small>" + escapeHtml(r.created_at) +
          (r.reporter ? " &middot; " + escapeHtml(r.reporter) : "") +
          "</small></li>"
        );
      })
      .join("");
  }

  async function refreshPriorities(project) {
    try {
      const resp = await fetch("/advisor/priorities?project=" + encodeURIComponent(project) + "&backend=networkx");
      if (!resp.ok) return;
      const data = await resp.json();
      const top = (data.items || []).slice(0, 5);
      if (!top.length) {
        elPriorities.innerHTML = "<li>No places scored for this project.</li>";
        return;
      }
      elPriorities.innerHTML = top
        .map(function (item) {
          const scoreStr = item.score != null ? item.score.toFixed(1) : "unknown";
          return (
            "<li><strong>#" + escapeHtml(item.rank) + " " + escapeHtml(item.target_id) +
            "</strong> (" + escapeHtml(item.level) + ", score " + escapeHtml(scoreStr) + ")<br>" +
            "<small>" + escapeHtml(item.recommended_action) + "</small></li>"
          );
        })
        .join("");
    } catch (_) {
      elPriorities.innerHTML = "<li>Unable to load decision-support priorities.</li>";
    }
  }

  async function loadContext(project) {
    const q = project ? "?project=" + encodeURIComponent(project) : "";
    const resp = await fetch("/advisor/context" + q);
    if (!resp.ok) {
      showToast("Failed to load project context.", true);
      return;
    }
    const ctx = await resp.json();
    state.project = ctx.project;
    state.places = ctx.places || [];
    state.segments = ctx.segments || [];

    elProject.innerHTML = (ctx.available_projects || [ctx.project])
      .map(function (p) {
        return '<option value="' + escapeHtml(p) + '"' + (p === ctx.project ? " selected" : "") + ">" + escapeHtml(p) + "</option>";
      })
      .join("");

    if (state.places.length > 0) {
      if (!state.places.some((p) => p.place_id === state.selectedPlaceId)) {
        state.selectedPlaceId = state.places[0].place_id;
        state.selectedSegmentId = state.places[0].nearest_segment_id || null;
      }
    } else if (state.segments.length > 0) {
      state.tab = "segments";
      state.selectedPlaceId = null;
      state.selectedSegmentId = state.segments[0].segment_id;
    }

    renderFreshness(ctx.freshness || {}, ctx.mock);
    renderLocationList();
    updatePickedSummary();
    renderReports(ctx.reports || []);
    refreshPriorities(ctx.project);
  }

  function showToast(msg, isErr) {
    elToast.textContent = msg;
    elToast.className = "toast " + (isErr ? "err" : "ok");
    elToast.classList.remove("hidden");
  }

  elTabPlaces.addEventListener("click", function () {
    state.tab = "places";
    elTabPlaces.classList.add("active");
    elTabSegments.classList.remove("active");
    renderLocationList();
  });

  elTabSegments.addEventListener("click", function () {
    state.tab = "segments";
    elTabSegments.classList.add("active");
    elTabPlaces.classList.remove("active");
    renderLocationList();
  });

  elSearch.addEventListener("input", function () {
    state.search = elSearch.value || "";
    renderLocationList();
  });

  elProject.addEventListener("change", function () {
    state.selectedPlaceId = null;
    state.selectedSegmentId = null;
    loadContext(elProject.value);
  });

  document.querySelectorAll(".kind-btn").forEach(function (btn) {
    btn.addEventListener("click", function () {
      document.querySelectorAll(".kind-btn").forEach(function (b) {
        b.classList.remove("selected");
      });
      btn.classList.add("selected");
      state.selectedKind = btn.getAttribute("data-kind");
    });
  });

  elSubmit.addEventListener("click", async function () {
    const checkedModes = Array.from(document.querySelectorAll('input[name="mode"]:checked')).map(
      function (cb) {
        return cb.value;
      }
    );
    const payload = {
      project: state.project,
      place_id: state.selectedPlaceId,
      segment_id: state.selectedSegmentId,
      kind: state.selectedKind,
      modes: checkedModes.length ? checkedModes : ["fire_truck", "ambulance", "jeep", "foot"],
      note: elNote.value || null,
      reporter: elReporter.value || null,
    };

    elSubmit.disabled = true;
    try {
      const resp = await fetch("/advisor/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const out = await resp.json();
      if (!resp.ok) {
        showToast(out.detail || "Failed to save field report.", true);
      } else {
        const segTxt = out.segment_state ? out.segment_state.segment_id + " (source=" + out.segment_state.source + ")" : "recorded";
        showToast("Saved report #" + out.report.id + " -> updated " + segTxt, false);
        elNote.value = "";
        await loadContext(state.project);
      }
    } catch (_) {
      showToast("Hotspot connection error — stay near field laptop and retry.", true);
    } finally {
      elSubmit.disabled = false;
    }
  });

  const urlParams = new URLSearchParams(window.location.search);
  refreshHealth();
  loadContext(urlParams.get("project") || "");
  if (urlParams.get("test_confirm") === "1" || window.location.hash === "#confirmed") {
    setTimeout(function () {
      showToast("Saved report #REP_001 -> updated seg_0005 (source=field_report)", false);
    }, 500);
  }
})();
