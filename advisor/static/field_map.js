/* Typhon Field Map (/field/map): tap a road, say what you see, say how bad, send.
   Draws every road of the project on a plain <canvas> from /advisor/fieldmap, so it works on the
   laptop hotspot with no internet and no tile server. Status colours come from the same advisor rules
   as the dashboard; a report goes to the same POST /advisor/reports as the form view. */
(function () {
  "use strict";

  // ---------- constants ----------
  const VEH = [
    ["ambulance", "\u{1F691}", "Ambulance"],
    ["fire_truck", "\u{1F692}", "Fire truck"],
    ["jeep", "\u{1F699}", "Jeep"],
    ["foot", "\u{1F6B6}", "Foot"],
  ];
  const VEH_ICON = Object.fromEntries(VEH.map((v) => [v[0], v[1]]));
  const VEH_NAME = Object.fromEntries(VEH.map((v) => [v[0], v[2]]));
  const ALL = ["fire_truck", "ambulance", "jeep", "foot"];
  const COLORS = { open: "#2E7D4F", partial: "#C98A12", blocked: "#B3261E", unknown: "#8C918A" };

  // What the responder saw -> report kind (advisor/assess.py rules decide what that does to the road)
  const PROBLEMS = [
    { id: "landslide", icon: "\u{1FAA8}", label: "Landslide / debris", sub: "Mud, rocks on the road", kind: "new_debris", sev: true },
    { id: "tree", icon: "\u{1F333}", label: "Fallen tree", sub: "Trees or poles across", kind: "new_debris", sev: true },
    { id: "washout", icon: "\u{1F30A}", label: "Washed out / flooded", sub: "Water, road surface gone", kind: "dead_end", sev: true },
    { id: "bridge", icon: "\u{1F309}", label: "Bridge / culvert broken", sub: "Crossing damaged", kind: "dead_end", sev: true },
    { id: "clear", icon: "\u2705", label: "Road is clear", sub: "Open, all vehicles pass", kind: "cleared", sev: false, cls: "good", wide: true },
    { id: "other", icon: "\u{1F4DD}", label: "Something else", sub: "A note only, status unchanged", kind: "other", sev: false, wide: true },
  ];
  const CHECKS = [
    { id: "confirm", icon: "\u{1F44D}", label: "Yes, it is blocked", sub: "Confirm what the model flagged", kind: "confirm", sev: false, cls: "check" },
    { id: "reject", icon: "\u{1F44E}", label: "No, false alarm", sub: "Model was wrong here", kind: "reject", sev: false, cls: "check" },
  ];
  // How bad -> which vehicles can no longer pass (a report blocks only the vehicles it names)
  const SEVERITY = [
    { id: "total", label: "Completely blocked", sub: "Nobody can get through, not even on foot", modes: ALL },
    { id: "foot", label: "Only on foot", sub: "People can climb over; no vehicle passes", modes: ["fire_truck", "ambulance", "jeep"] },
    { id: "small", label: "Narrowed", sub: "Jeep and ambulance squeeze past; fire truck cannot", modes: ["fire_truck"] },
  ];

  // ---------- state ----------
  const S = {
    project: new URLSearchParams(location.search).get("project") || "",
    vehicle: "ambulance",
    data: null,
    access: null,
    roads: [],
    byId: {},
    places: [],
    sel: null,
    selPlace: null,
    step: 0,
    problem: null,
    sev: null,
    lastId: 0,
    busy: false,
    flash: {}, // road id -> time it changed (for a glow)
    result: null,
  };

  const $ = (id) => document.getElementById(id);
  const canvas = $("fm-canvas");
  const ctx = canvas.getContext("2d");
  const base = document.createElement("canvas");
  const bctx = base.getContext("2d");
  const panel = $("fm-panel");
  let W = 0, H = 0, DPR = 1;
  let K = 1; // cos(latitude) so the map is not stretched
  const V = { cx: 0, cy: 0, s: 1 };
  let baseDirty = true;
  let anim = null;

  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(r.status + " " + url);
    return r.json();
  }
  const q = () => "?project=" + encodeURIComponent(S.project);

  // ---------- geometry ----------
  function toS(x, y) { return [(x - V.cx) * V.s + W / 2, (y - V.cy) * V.s + H / 2]; }
  function toW(sx, sy) { return [(sx - W / 2) / V.s + V.cx, (sy - H / 2) / V.s + V.cy]; }

  function prepare(data) {
    let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity, latSum = 0, n = 0;
    data.roads.forEach((r) => r.c.forEach((l) => l.forEach((p) => { latSum += p[1]; n++; })));
    K = Math.cos(((n ? latSum / n : 0) * Math.PI) / 180);
    S.roads = data.roads.map((r) => {
      const lines = r.c.map((l) => l.map((p) => [p[0] * K, -p[1]]));
      let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
      lines.forEach((l) => l.forEach((p) => {
        if (p[0] < bx0) bx0 = p[0]; if (p[0] > bx1) bx1 = p[0];
        if (p[1] < by0) by0 = p[1]; if (p[1] > by1) by1 = p[1];
      }));
      minx = Math.min(minx, bx0); maxx = Math.max(maxx, bx1); miny = Math.min(miny, by0); maxy = Math.max(maxy, by1);
      const mid = midpoint(lines);
      const major = /trunk|primary|secondary|tertiary/.test(r.hw);
      return Object.assign({}, r, { lines, bb: [bx0, by0, bx1, by1], mid, major });
    });
    S.byId = Object.fromEntries(S.roads.map((r) => [r.id, r]));
    S.places = data.places.map((p) => Object.assign({}, p, { w: [p.c[0] * K, -p.c[1]] }));
    S.bounds = [minx, miny, maxx, maxy];
  }

  function midpoint(lines) {
    const l = lines.reduce((a, b) => (b.length > a.length ? b : a), lines[0] || []);
    if (!l.length) return [0, 0];
    let total = 0;
    for (let i = 1; i < l.length; i++) total += Math.hypot(l[i][0] - l[i - 1][0], l[i][1] - l[i - 1][1]);
    let acc = 0;
    for (let i = 1; i < l.length; i++) {
      const d = Math.hypot(l[i][0] - l[i - 1][0], l[i][1] - l[i - 1][1]);
      if (acc + d >= total / 2) {
        const t = d ? (total / 2 - acc) / d : 0;
        return [l[i - 1][0] + t * (l[i][0] - l[i - 1][0]), l[i - 1][1] + t * (l[i][1] - l[i - 1][1])];
      }
      acc += d;
    }
    return l[0];
  }

  function fit(bb, pad) {
    const [x0, y0, x1, y1] = bb;
    const panelW = W > 760 ? 424 : 0;
    const usableW = W - panelW, usableH = W > 760 ? H : H * 0.55;
    const s = Math.min((usableW - 2 * pad) / Math.max(x1 - x0, 1e-6), (usableH - 2 * pad) / Math.max(y1 - y0, 1e-6));
    const cx = (x0 + x1) / 2 + panelW / 2 / s;
    const cy = (y0 + y1) / 2 + (W > 760 ? 0 : (H * 0.45) / 2 / s);
    return { cx, cy, s };
  }

  function flyTo(target, ms) {
    const from = { cx: V.cx, cy: V.cy, s: V.s };
    const t0 = performance.now();
    anim = function (now) {
      const t = Math.min(1, (now - t0) / (ms || 600));
      const e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      V.s = Math.exp(Math.log(from.s) + (Math.log(target.s) - Math.log(from.s)) * e);
      V.cx = from.cx + (target.cx - from.cx) * e;
      V.cy = from.cy + (target.cy - from.cy) * e;
      baseDirty = true;
      if (t >= 1) anim = null;
    };
  }

  function zoomAt(sx, sy, f) {
    const [wx, wy] = toW(sx, sy);
    V.s = Math.max(10, Math.min(V.s * f, 5e7));
    V.cx = wx - (sx - W / 2) / V.s;
    V.cy = wy - (sy - H / 2) / V.s;
    baseDirty = true;
  }

  // ---------- drawing ----------
  function resize() {
    DPR = window.devicePixelRatio || 1;
    W = canvas.clientWidth; H = canvas.clientHeight;
    canvas.width = base.width = Math.round(W * DPR);
    canvas.height = base.height = Math.round(H * DPR);
    baseDirty = true;
  }

  function statusOf(r) { return (r.st && r.st[S.vehicle]) || "unknown"; }

  function roadWidth(r) {
    const z = Math.log2(V.s / 1e4); // grows as you zoom in
    const w = (r.major ? 3.2 : 2.0) + Math.max(0, z) * (r.major ? 0.9 : 0.6);
    return Math.min(w, r.major ? 11 : 8);
  }

  function pathFor(r, path) {
    for (const l of r.lines) {
      for (let i = 0; i < l.length; i++) {
        const [x, y] = toS(l[i][0], l[i][1]);
        if (i === 0) path.moveTo(x, y); else path.lineTo(x, y);
      }
    }
  }

  function visible(r) {
    const [x0, y0] = toS(r.bb[0], r.bb[1]);
    const [x1, y1] = toS(r.bb[2], r.bb[3]);
    return !(x1 < -20 || x0 > W + 20 || y1 < -20 || y0 > H + 20);
  }

  function drawBase() {
    bctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    bctx.clearRect(0, 0, W, H);
    bctx.lineCap = "round"; bctx.lineJoin = "round";
    const groups = { unknown: [], open: [], partial: [], blocked: [] };
    S.roads.forEach((r) => { if (visible(r)) groups[statusOf(r)] ? groups[statusOf(r)].push(r) : groups.unknown.push(r); });
    const order = ["unknown", "open", "partial", "blocked"];
    // white casing under everything so roads read on the sand background
    for (const st of order) {
      for (const r of groups[st]) {
        const p = new Path2D(); pathFor(r, p);
        bctx.strokeStyle = "rgba(255,255,255,.95)"; bctx.lineWidth = roadWidth(r) + 3; bctx.setLineDash([]);
        bctx.stroke(p);
      }
    }
    for (const st of order) {
      bctx.strokeStyle = COLORS[st];
      bctx.setLineDash(st === "partial" ? [9, 6] : st === "unknown" ? [2, 5] : []);
      for (const r of groups[st]) {
        const p = new Path2D(); pathFor(r, p);
        bctx.lineWidth = roadWidth(r) * (st === "unknown" ? 0.8 : 1);
        bctx.stroke(p);
      }
    }
    bctx.setLineDash([]);
    // a cross on blocked roads once zoomed in enough to see them
    if (V.s > 2e4) {
      for (const r of groups.blocked) {
        const [x, y] = toS(r.mid[0], r.mid[1]);
        cross(bctx, x, y, 6);
      }
    }
    // needs-checking outline (model raised a suspicion; a person has not looked yet)
    bctx.strokeStyle = "rgba(201,138,18,.55)"; bctx.setLineDash([3, 4]);
    S.roads.forEach((r) => {
      if (r.verify && visible(r)) { const p = new Path2D(); pathFor(r, p); bctx.lineWidth = roadWidth(r) + 9; bctx.stroke(p); }
    });
    bctx.setLineDash([]);
    baseDirty = false;
  }

  function cross(c, x, y, s) {
    c.save();
    c.strokeStyle = "#fff"; c.lineWidth = 5;
    c.beginPath(); c.moveTo(x - s, y - s); c.lineTo(x + s, y + s); c.moveTo(x + s, y - s); c.lineTo(x - s, y + s); c.stroke();
    c.strokeStyle = COLORS.blocked; c.lineWidth = 2.5; c.stroke();
    c.restore();
  }

  function badge(c, x, y, text, bg, fg) {
    c.save();
    c.font = "700 12px system-ui, sans-serif";
    const w = Math.max(22, c.measureText(text).width + 12);
    c.fillStyle = bg; c.strokeStyle = "#fff"; c.lineWidth = 2;
    roundRect(c, x - w / 2, y - 11, w, 22, 11); c.fill(); c.stroke();
    c.fillStyle = fg; c.textAlign = "center"; c.textBaseline = "middle"; c.fillText(text, x, y + 0.5);
    c.restore();
  }
  function roundRect(c, x, y, w, h, r) {
    c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
    c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
  }

  function placeState(p) {
    const ap = (S.access && S.access.places || []).find((a) => a.place_id === p.id);
    if (!ap) return "unknown";
    if (S.access.base_place_id === p.id) return "base";
    const v = ap.reachable && ap.reachable[S.vehicle];
    return v === true ? "ok" : v === false ? "cut" : "unknown";
  }

  function frame(now) {
    if (anim) anim(now);
    if (baseDirty) drawBase();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(base, 0, 0);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    const pulse = (Math.sin(now / 300) + 1) / 2;

    // Clear First (reopen plan) and Fly Next highlights
    const reopen = ((S.access && S.access.reopen_plan) || []).filter((r) => !r.mode || r.mode === S.vehicle).slice(0, 3);
    reopen.forEach((rp, i) => {
      const r = S.byId[rp.segment_id]; if (!r) return;
      const p = new Path2D(); pathFor(r, p);
      ctx.strokeStyle = "rgba(181,211,52," + (0.45 + 0.35 * pulse) + ")"; ctx.lineWidth = roadWidth(r) + 10; ctx.stroke(p);
      const [x, y] = toS(r.mid[0], r.mid[1]); badge(ctx, x, y - 16, "#" + (i + 1), "#B5D334", "#0F1E3D");
    });
    ((S.access && S.access.fly_next) || []).slice(0, 3).forEach((fn, i) => {
      const r = S.byId[fn.segment_id]; if (!r) return;
      const p = new Path2D(); pathFor(r, p);
      ctx.setLineDash([6, 6]); ctx.lineDashOffset = -now / 40;
      ctx.strokeStyle = "#2A4EA8"; ctx.lineWidth = roadWidth(r) + 5; ctx.stroke(p);
      ctx.setLineDash([]);
      const [x, y] = toS(r.mid[0], r.mid[1]); badge(ctx, x, y + 16, "\u2708" + (i + 1), "#2A4EA8", "#fff");
    });

    // roads that just changed glow for a few seconds
    for (const id in S.flash) {
      const age = (now - S.flash[id]) / 1000;
      const r = S.byId[id];
      if (!r || age > 4) { delete S.flash[id]; continue; }
      const p = new Path2D(); pathFor(r, p);
      ctx.strokeStyle = "rgba(255,214,0," + (1 - age / 4) + ")"; ctx.lineWidth = roadWidth(r) + 18 * (1 - age / 4) + 4; ctx.stroke(p);
      ctx.strokeStyle = COLORS[statusOf(r)] || COLORS.unknown; ctx.lineWidth = roadWidth(r); ctx.stroke(p);
    }

    // selected road
    if (S.sel && S.byId[S.sel]) {
      const r = S.byId[S.sel];
      const p = new Path2D(); pathFor(r, p);
      ctx.strokeStyle = "rgba(42,78,168," + (0.25 + 0.25 * pulse) + ")"; ctx.lineWidth = roadWidth(r) + 16; ctx.stroke(p);
      ctx.strokeStyle = "#fff"; ctx.lineWidth = roadWidth(r) + 4; ctx.stroke(p);
      ctx.strokeStyle = COLORS[statusOf(r)] || COLORS.unknown; ctx.lineWidth = roadWidth(r); ctx.stroke(p);
      const [x, y] = toS(r.mid[0], r.mid[1]);
      pin(ctx, x, y);
    }

    // places
    const showNames = V.s > 6e3;
    S.places.forEach((pl) => {
      const [x, y] = toS(pl.w[0], pl.w[1]);
      if (x < -40 || x > W + 40 || y < -40 || y > H + 40) return;
      const st = placeState(pl);
      const col = st === "cut" ? COLORS.blocked : st === "ok" ? COLORS.open : st === "base" ? "#0F1E3D" : COLORS.unknown;
      if (st === "cut") {
        ctx.beginPath(); ctx.arc(x, y, 9 + 10 * pulse, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(179,38,30," + (0.35 - 0.3 * pulse) + ")"; ctx.fill();
      }
      ctx.beginPath(); ctx.arc(x, y, st === "base" ? 9 : 7, 0, Math.PI * 2);
      ctx.fillStyle = col; ctx.fill(); ctx.lineWidth = 2.5; ctx.strokeStyle = "#fff"; ctx.stroke();
      if (st === "base") { ctx.fillStyle = "#B5D334"; ctx.font = "700 10px system-ui"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText("H", x, y + 0.5); }
      if (S.selPlace === pl.id) { ctx.beginPath(); ctx.arc(x, y, 13, 0, Math.PI * 2); ctx.strokeStyle = "#2A4EA8"; ctx.lineWidth = 3; ctx.stroke(); }
      if (showNames) {
        ctx.font = "600 12px system-ui, sans-serif"; ctx.textAlign = "left"; ctx.textBaseline = "middle";
        const label = String(pl.name || pl.id).slice(0, 28) + (st === "cut" ? "  \u2014 CUT OFF" : "");
        ctx.lineWidth = 4; ctx.strokeStyle = "rgba(255,255,255,.95)"; ctx.strokeText(label, x + 12, y);
        ctx.fillStyle = st === "cut" ? COLORS.blocked : "#0F1E3D"; ctx.fillText(label, x + 12, y);
      }
    });
    requestAnimationFrame(frame);
  }

  function pin(c, x, y) {
    c.save();
    c.translate(x, y - 4);
    c.fillStyle = "#2A4EA8"; c.strokeStyle = "#fff"; c.lineWidth = 2.5;
    c.beginPath(); c.moveTo(0, 0); c.bezierCurveTo(-12, -16, -12, -30, 0, -30); c.bezierCurveTo(12, -30, 12, -16, 0, 0); c.closePath();
    c.fill(); c.stroke();
    c.beginPath(); c.arc(0, -20, 4.5, 0, Math.PI * 2); c.fillStyle = "#fff"; c.fill();
    c.restore();
  }

  // ---------- picking ----------
  function distSeg(px, py, ax, ay, bx, by) {
    const dx = bx - ax, dy = by - ay;
    const l2 = dx * dx + dy * dy;
    let t = l2 ? ((px - ax) * dx + (py - ay) * dy) / l2 : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
  }

  function pick(sx, sy) {
    for (const pl of S.places) {
      const [x, y] = toS(pl.w[0], pl.w[1]);
      if (Math.hypot(x - sx, y - sy) < 20) return { place: pl };
    }
    const tol = 26;
    const [wx, wy] = toW(sx, sy);
    const wt = tol / V.s;
    let best = null, bestD = tol;
    for (const r of S.roads) {
      if (wx < r.bb[0] - wt || wx > r.bb[2] + wt || wy < r.bb[1] - wt || wy > r.bb[3] + wt) continue;
      for (const l of r.lines) {
        for (let i = 1; i < l.length; i++) {
          const a = toS(l[i - 1][0], l[i - 1][1]), b = toS(l[i][0], l[i][1]);
          const d = distSeg(sx, sy, a[0], a[1], b[0], b[1]);
          if (d < bestD) { bestD = d; best = r; }
        }
      }
    }
    return best ? { road: best } : null;
  }

  // ---------- gestures (one finger pans, two fingers pinch, tap selects) ----------
  const ptrs = new Map();
  let gesture = null;
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    ptrs.set(e.pointerId, { x: e.offsetX, y: e.offsetY });
    anim = null;
    if (ptrs.size === 1) gesture = { x0: e.offsetX, y0: e.offsetY, t0: performance.now(), moved: 0, multi: false };
    else if (gesture) gesture.multi = true;
  });
  canvas.addEventListener("pointermove", (e) => {
    const prev = ptrs.get(e.pointerId);
    if (!prev) return;
    const cur = { x: e.offsetX, y: e.offsetY };
    if (ptrs.size === 1) {
      V.cx -= (cur.x - prev.x) / V.s; V.cy -= (cur.y - prev.y) / V.s;
      if (gesture) gesture.moved += Math.hypot(cur.x - prev.x, cur.y - prev.y);
      baseDirty = true;
    } else if (ptrs.size === 2) {
      const other = [...ptrs.entries()].find(([id]) => id !== e.pointerId)[1];
      const d0 = Math.hypot(prev.x - other.x, prev.y - other.y);
      const d1 = Math.hypot(cur.x - other.x, cur.y - other.y);
      const mx0 = (prev.x + other.x) / 2, my0 = (prev.y + other.y) / 2;
      const mx1 = (cur.x + other.x) / 2, my1 = (cur.y + other.y) / 2;
      V.cx -= (mx1 - mx0) / V.s; V.cy -= (my1 - my0) / V.s;
      if (d0 > 0) zoomAt(mx1, my1, d1 / d0);
    }
    ptrs.set(e.pointerId, cur);
  });
  function endPtr(e) {
    ptrs.delete(e.pointerId);
    if (ptrs.size === 0 && gesture) {
      if (!gesture.multi && gesture.moved < 10 && performance.now() - gesture.t0 < 600) onTap(e.offsetX, e.offsetY);
      gesture = null;
    }
  }
  canvas.addEventListener("pointerup", endPtr);
  canvas.addEventListener("pointercancel", endPtr);
  canvas.addEventListener("wheel", (e) => { e.preventDefault(); zoomAt(e.offsetX, e.offsetY, Math.exp(-e.deltaY * 0.0015)); }, { passive: false });
  canvas.addEventListener("dblclick", (e) => zoomAt(e.offsetX, e.offsetY, 2));
  $("fm-zin").onclick = () => zoomAt(W / 2, H / 2, 1.6);
  $("fm-zout").onclick = () => zoomAt(W / 2, H / 2, 1 / 1.6);
  $("fm-fit").onclick = () => flyTo(fit(S.bounds, 30), 500);
  window.addEventListener("resize", resize);

  function onTap(sx, sy) {
    const hit = pick(sx, sy);
    if (!hit) { if (S.sel && S.step < 3) deselect(); return; }
    if (hit.place) {
      S.selPlace = hit.place.id;
      selectRoad(hit.place.seg, true);
    } else {
      S.selPlace = null;
      selectRoad(hit.road.id, false);
    }
  }

  function selectRoad(id, keepPlace) {
    if (!id || !S.byId[id]) { toast("This place has no road joined to it.", true); return; }
    if (!keepPlace) S.selPlace = null;
    S.sel = id; S.step = 1; S.problem = null; S.sev = null; S.result = null;
    $("fm-hint").classList.add("hidden");
    renderPanel();
  }

  function focusRoad(id) {
    const r = S.byId[id]; if (!r) return;
    const span = Math.max(r.bb[2] - r.bb[0], r.bb[3] - r.bb[1], 0.0015);
    const t = fit([r.mid[0] - span, r.mid[1] - span, r.mid[0] + span, r.mid[1] + span], 40);
    flyTo(t, 700);
    selectRoad(id, false);
  }

  function deselect() {
    S.sel = null; S.selPlace = null; S.step = 0; S.result = null;
    $("fm-hint").classList.remove("hidden");
    renderPanel();
  }

  // ---------- panel ----------
  function statusChips(r) {
    return '<div class="chips">' + VEH.map(([k, ic, name]) => {
      const st = (r.st && r.st[k]) || "unknown";
      return '<span class="chip ' + st + '" title="' + esc(name) + '">' + ic + " " + esc(st === "unknown" ? "not seen" : st) + "</span>";
    }).join("") + (r.verify ? '<span class="chip verify">\u26A0 needs checking</span>' : "") + "</div>";
  }

  function roadTitle(r) {
    const hw = String(r.hw || "road").replace(/_/g, " ");
    return (r.name ? esc(r.name) : esc(hw.charAt(0).toUpperCase() + hw.slice(1))) +
      ' <span class="muted">' + esc(r.id) + (r.len ? " \u00B7 " + Math.round(r.len) + " m" : "") + "</span>";
  }

  function steps(n) {
    return '<div class="steps">' + [1, 2, 3].map((i) => '<span class="' + (i <= n ? "on" : "") + '"></span>').join("") + "</div>";
  }

  function vehStrip(modes) {
    return '<div class="veh">' + VEH.map(([k, ic]) => '<span class="' + (modes.includes(k) ? "x" : "") + '">' + ic + "</span>").join("") + "</div>";
  }

  function renderPanel() {
    panel.classList.remove("collapsed");
    if (!S.sel) return renderOverview();
    const r = S.byId[S.sel];
    const place = S.selPlace ? S.places.find((p) => p.id === S.selPlace) : null;
    let h = '<button class="close" type="button" data-act="close" aria-label="Close">\u2715</button>';
    h += "<h2>" + roadTitle(r) + "</h2>";
    if (place) h += '<div class="muted">Near ' + esc(place.name) + "</div>";
    h += statusChips(r);

    if (S.busy) {
      h += '<div class="sending-overlay"><span class="spinner"></span> <b>Updating road and recomputing plan\u2026</b></div>';
      panel.innerHTML = h;
      return;
    }

    if (S.result) return renderResult(h);

    if (r.p_blocked != null && (r.verify || r.p_blocked >= 0.5)) {
      h += '<div class="suspect"><b>Model suspicion:</b> ' + Math.round(r.p_blocked * 100) +
        "% chance of debris from the drone image. A model never decides the road \u2014 please check it." +
        (r.crop ? '<img alt="Drone crop of this road" src="/advisor/evidence?path=' + encodeURIComponent(r.crop) + '">' : "") + "</div>";
    }

    // 1-Tap Quick Action Row
    h += '<div class="quick-row">' +
      '<button type="button" class="quick-btn block" data-act="quick-block"><span class="q-ic">\u{1F6D1}</span><div><b>Block Road</b><small>1-Tap Report</small></div></button>' +
      '<button type="button" class="quick-btn clear" data-act="quick-clear"><span class="q-ic">\u2705</span><div><b>Mark Open</b><small>1-Tap Report</small></div></button>' +
      '</div>';

    // Interactive Problem Grid
    const opts = (r.verify || r.p_blocked != null) ? CHECKS.concat(PROBLEMS) : PROBLEMS;
    h += '<div class="section-title">Or choose problem:</div><div class="grid">';
    h += opts.map((o) => card(o, S.problem && S.problem.id === o.id, "problem")).join("") + "</div>";

    // If problem requires severity, show severity options directly below
    if (S.problem && S.problem.sev) {
      h += '<div class="sev-section">';
      h += '<div class="section-title">How bad is it? (Tap to submit immediately)</div><div class="grid">';
      h += SEVERITY.map((s) => '<button type="button" class="card wide' + (S.sev && S.sev.id === s.id ? " sel" : "") + '" data-sev="' + s.id + '">' +
        "<div><b>" + esc(s.label) + "</b><small>" + esc(s.sub) + "</small>" + vehStrip(s.modes) + "</div></button>").join("");
      h += "</div></div>";
    }

    // Collapsible note / custom team info
    h += '<details style="margin-top:14px"><summary class="muted">Add note or callsign</summary>' +
      '<label class="f" for="fm-note">Note</label><textarea id="fm-note" placeholder="e.g. Boulder on road"></textarea>' +
      '<label class="f" for="fm-team">Team / callsign</label><input type="text" id="fm-team" placeholder="e.g. NDRF Team-2" value="' + esc(sessionGet("typhon_team")) + '">' +
      '<label class="f" for="fm-pin">Field PIN (optional)</label><input type="text" id="fm-pin" inputmode="numeric" maxlength="6" placeholder="6 digits" value="' + esc(sessionGet("vortex_field_pin")) + '">' +
      '<button class="send" type="button" data-act="send" id="fm-send">Send custom report</button>' +
      '</details>';

    panel.innerHTML = h;
  }

  function card(o, sel, kind) {
    return '<button type="button" class="card' + (o.wide ? " wide" : "") + (o.cls ? " " + o.cls : "") + (sel ? " sel" : "") + '" data-' + kind + '="' + o.id + '">' +
      '<span class="ic">' + o.icon + "</span><div><b>" + esc(o.label) + "</b><small>" + esc(o.sub) + "</small></div></button>";
  }

  function reportModes() {
    if (!S.problem) return ALL;
    if (S.problem.sev && S.sev) return S.sev.modes;
    return ALL;
  }

  function effectText(modes) {
    const k = S.problem.kind;
    if (k === "cleared") return "The road will show OPEN for every vehicle.";
    if (k === "other") return "Saved as a note for the operator; the road colour does not change.";
    if (k === "reject") return "The model's suspicion is dropped; the road goes back to what the measurements say.";
    if (k === "confirm") return "The road will show BLOCKED for every vehicle.";
    return "The road will show BLOCKED for " + modes.map((m) => VEH_NAME[m].toLowerCase()).join(", ") + ".";
  }

  function renderResult(h) {
    const R = S.result;
    const worse = R.after > R.before, better = R.after < R.before;
    h += '<div class="result"><div class="big">' + (better ? "\u{1F7E2}" : worse ? "\u{1F534}" : "\u2705") + "</div>";
    h += "<b>Report #" + esc(R.id) + " saved & live on laptop</b><div class=\"muted\">" + esc(R.text) + "</div>";
    h += '<div class="delta">' + R.before + " \u2192 <em class=\"" + (better ? "good" : "") + '">' + R.after + "</em></div>";
    h += '<div class="muted">places cut off for ' + esc(VEH_NAME[S.vehicle].toLowerCase()) + " \u00B7 plan recomputed in " + R.secs + " s</div></div>";
    if (R.reopenTop) h += '<h3>Clear first now</h3><ul class="list"><li class="tap" data-road="' + esc(R.reopenTop.segment_id) + '"><span class="badge c">#1</span>Clear <b>' + esc(R.reopenTop.segment_id) + "</b> \u2014 reconnects " + esc(R.reopenTop.reconnects_people || 0) + " people, " + esc(R.reopenTop.reconnects_places || 0) + " places</li></ul>";
    h += '<button class="send" type="button" data-act="again">Report another road</button>';
    panel.innerHTML = h;
  }

  function renderOverview() {
    let h = "<h2>Tap a road you can see</h2><div class=\"muted\">Pinch to zoom, drag to move. Tap a road or a village dot, then tell us what is there.</div>";
    const reopen = ((S.access && S.access.reopen_plan) || []).filter((r) => !r.mode || r.mode === S.vehicle).slice(0, 3);
    h += '<h3>Clear first <span class="muted">(reopens the most people)</span></h3>';
    h += reopen.length ? '<ul class="list">' + reopen.map((r, i) => '<li class="tap" data-road="' + esc(r.segment_id) + '"><span class="badge c">#' + (i + 1) + "</span><b>" + esc(r.segment_id) + "</b><br><small>Reconnects " + esc(r.reconnects_people || 0) + " people, " + esc(r.reconnects_places || 0) + " places" + (r.debris_volume_m3 != null ? " \u00B7 " + esc(r.debris_volume_m3) + " m\u00B3 debris" : "") + "</small></li>").join("") + "</ul>"
      : '<div class="muted">No blocked road is cutting anyone off.</div>';
    const fly = ((S.access && S.access.fly_next) || []).slice(0, 3);
    h += '<h3>Fly the drone next <span class="muted">(least known, most people behind)</span></h3>';
    h += fly.length ? '<ul class="list">' + fly.map((f, i) => '<li class="tap" data-road="' + esc(f.segment_id) + '"><span class="badge f">\u2708' + (i + 1) + "</span><b>" + esc(f.segment_id) + "</b><br><small>" + esc(f.dependent_population || 0) + " people depend on it" + (f.uncertainty != null ? " \u00B7 " + Math.round(f.uncertainty * 100) + "% unknown" : "") + "</small></li>").join("") + "</ul>"
      : '<div class="muted">Every road that matters has been seen.</div>';
    const cut = S.places.filter((p) => placeState(p) === "cut");
    if (cut.length) {
      h += "<h3>Cut off for " + esc(VEH_NAME[S.vehicle].toLowerCase()) + "</h3><ul class=\"list\">" + cut.slice(0, 8).map((p) => '<li class="tap" data-place="' + esc(p.id) + '">\u{1F534} <b>' + esc(p.name) + "</b>" + (p.pop != null ? " \u00B7 " + esc(p.pop) + " people" : "") + "</li>").join("") + "</ul>";
    }
    panel.innerHTML = h;
  }

  panel.addEventListener("click", (e) => {
    const t = e.target.closest("[data-act],[data-problem],[data-sev],[data-road],[data-place]");
    if (!t || S.busy) return;
    if (t.dataset.act === "quick-block") {
      S.problem = PROBLEMS.find((p) => p.id === "landslide") || { id: "landslide", label: "Landslide", kind: "dead_end", sev: true };
      S.sev = SEVERITY.find((s) => s.id === "total") || { id: "total", label: "Completely blocked", modes: ALL };
      send();
    } else if (t.dataset.act === "quick-clear") {
      S.problem = PROBLEMS.find((p) => p.id === "clear") || { id: "clear", label: "Road is clear", kind: "cleared", sev: false };
      S.sev = null;
      send();
    } else if (t.dataset.problem) {
      S.problem = CHECKS.concat(PROBLEMS).find((o) => o.id === t.dataset.problem);
      S.sev = null;
      if (!S.problem.sev) {
        // Clear, Confirm, Reject don't need severity -> send immediately!
        send();
      } else {
        renderPanel();
      }
    } else if (t.dataset.sev) {
      S.sev = SEVERITY.find((s) => s.id === t.dataset.sev);
      send();
    } else if (t.dataset.road) {
      focusRoad(t.dataset.road);
    } else if (t.dataset.place) {
      const p = S.places.find((x) => x.id === t.dataset.place);
      if (p) { S.selPlace = p.id; focusRoad(p.seg); S.selPlace = p.id; renderPanel(); }
    } else if (t.dataset.act === "close") {
      deselect();
    } else if (t.dataset.act === "again") {
      deselect();
    } else if (t.dataset.act === "send") {
      send();
    }
  });

  function sessionGet(k) { try { return sessionStorage.getItem(k) || ""; } catch (_) { return ""; } }
  function sessionSet(k, v) { try { sessionStorage.setItem(k, v); } catch (_) {} }

  function cutCount() {
    return ((S.access && S.access.places) || []).filter((p) => p.reachable && p.reachable[S.vehicle] === false).length;
  }

  // ---------- send ----------
  async function send() {
    if (S.busy) return;
    const note = ($("fm-note")?.value || "").trim();
    const team = ($("fm-team")?.value || sessionGet("typhon_team") || "").trim();
    const pin = ($("fm-pin")?.value || sessionGet("vortex_field_pin") || "").trim();
    sessionSet("typhon_team", team); sessionSet("vortex_field_pin", pin);
    const modes = reportModes();
    const probLabel = S.problem ? S.problem.label : "Obstruction";
    const tag = "[" + probLabel + (S.sev ? " \u00B7 " + S.sev.label : "") + "]";
    const payload = {
      project: S.project,
      segment_id: S.sel,
      place_id: S.selPlace || null,
      kind: S.problem ? S.problem.kind : "dead_end",
      modes: modes,
      note: (tag + (note ? " " + note : "")).slice(0, 500),
      reporter: team || null,
    };
    S.busy = true;
    renderPanel();
    const before = cutCount();
    const t0 = performance.now();
    try {
      const r = await fetch("/advisor/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Field-PIN": pin },
        body: JSON.stringify(payload),
      });
      const out = await r.json().catch(() => ({}));
      if (!r.ok) {
        toast(typeof out.detail === "string" ? out.detail : "The laptop refused the report (" + r.status + ").", true);
        S.busy = false;
        renderPanel();
        return;
      }
      S.lastId = out.report.id;
      const id = S.sel;
      await reload(false);
      const secs = ((performance.now() - t0) / 1000).toFixed(1);
      S.flash[id] = performance.now();
      const after = cutCount();
      const reopenTop = ((S.access && S.access.reopen_plan) || []).filter((x) => !x.mode || x.mode === S.vehicle)[0] || null;
      S.result = { id: out.report.id, before, after, secs, text: effectText(modes), reopenTop };
      S.step = 4;
      renderPanel();
      if (after !== before) bumpStats();
      toast("Report #" + out.report.id + " saved \u2014 places cut off " + before + " \u2192 " + after, false);
    } catch (_) {
      const kept = window.TyphonOutbox ? window.TyphonOutbox.keep(payload, { "X-Field-PIN": pin }) : 0;
      toast(kept ? "No signal: report kept on this device (" + kept + " waiting)." : "Cannot reach the laptop.", !kept);
      renderPanel();
    } finally {
      S.busy = false;
    }
  }

  // ---------- data ----------
  async function reload(refit) {
    const [data, access] = await Promise.all([
      getJSON("/advisor/fieldmap" + (S.project ? q() : "")),
      getJSON("/advisor/access?backend=networkx" + (S.project ? "&project=" + encodeURIComponent(S.project) : "")).catch(() => null),
    ]);
    const firstLoad = !S.data || S.project !== data.project;
    S.project = data.project;
    S.data = data;
    S.access = access;
    S.lastId = Math.max(S.lastId, data.last_report_id || 0);
    prepare(data);
    if (refit || firstLoad) Object.assign(V, fit(S.bounds, 30));
    renderProjects();
    renderStats();
    if (!S.sel || S.step === 0) renderPanel();
    baseDirty = true;
  }

  function renderProjects() {
    const sel = $("fm-project");
    sel.innerHTML = (S.data.available_projects || [S.project]).filter((p) => p !== "mock" || S.project === "mock")
      .map((p) => '<option value="' + esc(p) + '"' + (p === S.project ? " selected" : "") + ">" + esc(prettyProject(p)) + "</option>").join("");
  }
  function prettyProject(p) {
    if (p.startsWith("wayanad")) return "Wayanad (Recommended Demo)";
    if (p.startsWith("southfork")) return "South Fork (USGS)";
    if (p.startsWith("nepal")) return "Nepal (Slow / large dataset)";
    return p;
  }

  function renderStats() {
    const cut = ((S.access && S.access.places) || []).filter((p) => p.reachable && p.reachable[S.vehicle] === false);
    const people = cut.reduce((a, p) => a + (p.population || 0), 0);
    const blocked = S.roads.filter((r) => statusOf(r) === "blocked").length;
    const verify = S.roads.filter((r) => r.verify).length;
    $("fm-stats").innerHTML =
      '<div class="stat ' + (cut.length ? "alert" : "") + '" id="st-cut"><b>' + cut.length + "</b><small>places cut off" + (people ? " \u00B7 " + people + " people" : "") + "</small></div>" +
      '<div class="stat"><b>' + blocked + "</b><small>roads blocked for " + VEH_ICON[S.vehicle] + "</small></div>" +
      (verify ? '<div class="stat"><b>' + verify + "</b><small>need checking</small></div>" : "") +
      '<div class="stat"><b>' + (S.data.report_count || 0) + "</b><small>field reports</small></div>";
  }
  function bumpStats() {
    renderStats();
    const el = $("st-cut"); if (el) { el.classList.remove("bump"); void el.offsetWidth; el.classList.add("bump"); }
  }

  function renderVehicles() {
    $("fm-vehicles").innerHTML = VEH.map(([k, ic, name]) =>
      '<button type="button" role="radio" data-v="' + k + '" aria-checked="' + (k === S.vehicle) + '" title="' + name + '">' + ic + "<span>" + name + "</span></button>").join("");
  }
  $("fm-vehicles").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-v]"); if (!b) return;
    S.vehicle = b.dataset.v;
    renderVehicles(); renderStats(); baseDirty = true;
    renderPanel();
  });
  $("fm-project").addEventListener("change", async (e) => {
    S.project = e.target.value; S.sel = null; S.step = 0; S.result = null;
    setLive("Syncing\u2026", "");
    await fetch("/advisor/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project: S.project }),
    }).catch(() => {});
    reload(true).then(() => setLive("Live \u00B7 " + prettyProject(S.project), "ok")).catch(() => setLive("Server unreachable", "bad"));
  });

  let toastT = 0;
  function toast(msg, err) {
    const el = $("fm-toast");
    el.textContent = msg; el.className = "fm-toast" + (err ? " err" : "");
    clearTimeout(toastT); toastT = setTimeout(() => el.classList.add("hidden"), 5000);
  }
  function setLive(t, cls) { const el = $("fm-live"); el.textContent = t; el.className = "fm-live " + (cls || ""); }

  // Reports from other phones (or the form view) show up here within a few seconds
  async function poll() {
    try {
      const r = await getJSON("/advisor/reports" + q());
      const list = r.reports || [];
      const latest = list[list.length - 1];
      setLive("Live \u00B7 " + prettyProject(S.project), "ok");
      if (latest && latest.id > S.lastId && !S.busy) {
        S.lastId = latest.id;
        const before = cutCount();
        await reload(false);
        if (latest.segment_id) S.flash[latest.segment_id] = performance.now();
        const after = cutCount();
        toast("New report from " + (latest.reporter || "another team") + ": " + String(latest.kind).replace("_", " ") + " on " + (latest.segment_id || latest.place_id) +
          (after !== before ? " \u2014 places cut off " + before + " \u2192 " + after : ""), false);
        if (after !== before) bumpStats();
        if (!S.sel || S.step === 1) renderPanel(); // never wipe a half-written report
      }
    } catch (_) {
      setLive("Laptop not reachable", "bad");
    }
    setTimeout(poll, 4000);
  }

  // ---------- start ----------
  resize();
  renderVehicles();
  requestAnimationFrame(frame);
  reload(true)
    .then(() => { setLive("Live \u00B7 " + prettyProject(S.project), "ok"); setTimeout(poll, 4000); })
    .catch(() => { setLive("Server unreachable", "bad"); panel.innerHTML = "<h2>Cannot reach the laptop</h2><p class=\"muted\">Join the laptop's hotspot and reload this page.</p>"; });
})();
