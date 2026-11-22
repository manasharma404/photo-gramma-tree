// Home page v5 (22 Nov): the lead's Project Typhon illustration, rebuilt as particles.
// - Every particle is one sample of web/public/hero.webp (scripts/bake_hero_particles.py). In "detail" it sits where
//   it was in the picture, in its colour; in "wireframe" it moves onto a draped grid over the valley. The page sweeps
//   between the two every few seconds; the cursor (or a finger) gives the particles right under it a small nudge.
// - The picture is artwork, not our map: nothing here is presented as data. The measured numbers further down come
//   from story_anchors.json (scripts/bake_story_anchors.py, from the run files); none is typed in here.
import "@fontsource/inter/latin-300.css";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-800.css";
import "@fontsource/space-grotesk/latin-500.css";
import "@fontsource/space-grotesk/latin-600.css";
import * as THREE from "three";
import "./styles/tokens.css";
import "./styles/story.css";
import { mountIcons } from "./icons.js";
import particlesUrl from "./assets/hero_particles.bin?url";
import anchors from "./assets/story_anchors.json";

mountIcons();
const $ = (id) => document.getElementById(id);
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
const debug = (window.__story = { frames: 0, ready: false, n: 0, mix: 0, mode: "", error: null });
const clamp01 = (v) => Math.min(1, Math.max(0, v));
const ease = (t) => t * t * (3 - 2 * t);

// ---------- measured numbers (from the run files, via story_anchors.json) ----------
function fillNumbers() {
  const m = anchors.numbers?.map || {};
  const ph = anchors.numbers?.photos || {};
  const f = (v, d = 1) => (v == null ? "PENDING" : Number(v).toFixed(d));
  const vals = { minutes: f(m.minutes), area: f(m.area_ha, 2), photos: m.photos ?? "PENDING", rmse: f(m.rmse_h_m, 2),
    ncp: m.n_checkpoints ?? "PENDING", arrival: f(ph.arrival_to_map_s_typical, 1), worst: f(ph.arrival_to_map_s_worst, 1) };
  document.querySelectorAll("[data-num]").forEach((el) => { el.textContent = vals[el.dataset.num] ?? "PENDING"; });
}

// ---------- particles ----------
async function loadParticles(url) {
  const buf = await (await fetch(url)).arrayBuffer();
  const hl = new DataView(buf).getUint32(0, true);
  const head = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, hl)));
  const n = head.n;
  let o = 4 + hl;
  const i16 = () => { const a = new Int16Array(buf.slice(o, o + 2 * n)); o += 2 * n; return a; };
  const u8 = () => { const a = new Uint8Array(buf, o, n); o += n; return a; };
  const dx = i16(), dy = i16(), wx = i16(), wy = i16();
  const r = u8(), g = u8(), b = u8(), al = u8(), w = u8();
  return { head, n, dx, dy, wx, wy, r, g, b, al, w };
}

const VERT = /* glsl */ `
  attribute vec2 aDetail; attribute vec2 aWire; attribute vec3 aColor; attribute float aAlpha;
  attribute float aWeight; attribute float aRand;
  uniform vec2 uRes; uniform vec2 uOffset; uniform float uScale; uniform float uDpr; uniform float uTime;
  uniform float uMix; uniform vec2 uMouse; uniform float uHover; uniform float uW; uniform float uTop;
  uniform float uStep;
  varying vec3 vColor; varying float vAlpha; varying float vShape;
  const vec3 INK = vec3(0.141, 0.196, 0.122);
  const vec3 LIME = vec3(0.710, 0.827, 0.204);
  void main() {
    // the sweep: left to right, like a drone pass, with a little scatter
    float s = (aDetail.x / uW) * 0.55 + aRand * 0.12;
    float m = clamp(uMix * 1.67 - s, 0.0, 1.0);
    m = m * m * (3.0 - 2.0 * m);
    vec2 p = mix(aWire, aDetail, m);
    p.y -= sin(m * 3.14159) * (aRand - 0.5) * 36.0;                        // particles arc while they travel
    p.y += sin(uTime * 0.9 + aWire.x * 0.018) * 1.6 * (1.0 - m);            // the wireframe breathes
    // the cursor: a small nudge of the particles right under it, nothing more
    vec2 d = p - uMouse; float dist = length(d);
    float push = exp(-pow(dist / 26.0, 2.0)) * uHover;
    p += (dist > 0.001 ? d / dist : vec2(0.0)) * push * 9.0;
    vec2 screen = uOffset + vec2(p.x, p.y - uTop) * uScale;
    gl_Position = vec4(screen.x / uRes.x * 2.0 - 1.0, 1.0 - screen.y / uRes.y * 2.0, 0.0, 1.0);
    // the original home page's soft edge: an oval fade, and a fade before the bottom of the picture
    vec2 q = (aDetail - vec2(836.0, 452.0)) / vec2(970.0, 565.0);
    float edge = (1.0 - smoothstep(0.62, 1.0, length(q))) * (1.0 - smoothstep(880.0, 941.0, aDetail.y));
    vColor = mix(mix(INK, LIME * 0.75, push * 0.6), aColor, m);
    vAlpha = mix(aWeight * 0.85, aAlpha, m) * edge;
    vShape = m;
    float detailSize = uStep * uScale * (0.62 + 0.5 * aAlpha);
    float wireSize = 1.35 * uDpr;
    gl_PointSize = max(1.0, mix(wireSize, detailSize, m));
  }`;
const FRAG = /* glsl */ `
  precision mediump float;
  varying vec3 vColor; varying float vAlpha; varying float vShape;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = mix(length(c), max(abs(c.x), abs(c.y)), vShape);   // round in the wireframe, square in detail
    float a = vAlpha * (1.0 - smoothstep(0.42, 0.5, d));
    if (a < 0.02) discard;
    gl_FragColor = vec4(vColor, a);
  }`;

function buildPoints(P) {
  const { n, head } = P;
  const s = 1 / head.scale;
  const det = new Float32Array(n * 2), wir = new Float32Array(n * 2), col = new Float32Array(n * 3);
  const alp = new Float32Array(n), wgt = new Float32Array(n), rnd = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    det[2 * i] = P.dx[i] * s; det[2 * i + 1] = P.dy[i] * s;
    wir[2 * i] = P.wx[i] * s; wir[2 * i + 1] = P.wy[i] * s;
    col[3 * i] = P.r[i] / 255; col[3 * i + 1] = P.g[i] / 255; col[3 * i + 2] = P.b[i] / 255;
    alp[i] = P.al[i] / 255; wgt[i] = P.w[i] / 255;
    const h = Math.sin(i * 12.9898) * 43758.5453;
    rnd[i] = h - Math.floor(h);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(det, 2));   // unused by the shader; three wants one
  geo.setAttribute("aDetail", new THREE.BufferAttribute(det, 2));
  geo.setAttribute("aWire", new THREE.BufferAttribute(wir, 2));
  geo.setAttribute("aColor", new THREE.BufferAttribute(col, 3));
  geo.setAttribute("aAlpha", new THREE.BufferAttribute(alp, 1));
  geo.setAttribute("aWeight", new THREE.BufferAttribute(wgt, 1));
  geo.setAttribute("aRand", new THREE.BufferAttribute(rnd, 1));
  geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 1e6);    // never culled; skips three's 3D bounds check
  const uniforms = {
    uRes: { value: new THREE.Vector2(1, 1) }, uOffset: { value: new THREE.Vector2() }, uScale: { value: 1 },
    uDpr: { value: 1 }, uTime: { value: 0 }, uMix: { value: 0 }, uMouse: { value: new THREE.Vector2(-9999, -9999) },
    uHover: { value: 0 }, uW: { value: head.w }, uTop: { value: head.top }, uStep: { value: head.step },
  };
  const mat = new THREE.ShaderMaterial({ vertexShader: VERT, fragmentShader: FRAG, uniforms, transparent: true,
    depthTest: false, depthWrite: false });
  const pts = new THREE.Points(geo, mat);
  pts.frustumCulled = false;
  return { pts, uniforms };
}

// the view cycles: wireframe → detail (on load) → hold → wireframe → hold → detail …
const HOLD_DETAIL = 6.0, HOLD_WIRE = 2.6, TRAVEL = 1.9;

async function startHero() {
  const canvas = $("hero-canvas");
  const hero = $("hero");
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: true, powerPreference: "high-performance" });
  } catch (e) {
    debug.error = "webgl: " + e.message;
    hero.classList.add("no-gl");
    return;
  }
  const P = await loadParticles(particlesUrl);
  const { pts, uniforms: U } = buildPoints(P);
  const scene = new THREE.Scene();
  scene.add(pts);
  const cam = new THREE.Camera();
  debug.n = P.n;
  // (the picture is P.head.w wide; rows above P.head.top held the baked-in wordmark and are not used)
  const VALLEY_X = 880;                       // the valley's middle in the picture, kept in view on narrow screens

  // The picture runs from just over the headline to the bottom of the hero (its misty foot meets the page edge);
  // the side columns, the line of text and the button sit over its faded edges.
  const VIS = { x0: 160, x1: 1580, y0: P.head.top, y1: P.head.h };
  let dpr = 1, vw = 1, vh = 1, scale = 1, css = 1, offX = 0, offY = 0;
  const callouts = [...document.querySelectorAll(".hx-callout")];
  function placeCallouts() {
    callouts.forEach((el) => {
      const x = (offX + +el.dataset.px * scale) / dpr;
      const y = (offY + (+el.dataset.py - P.head.top) * scale) / dpr;
      const dy = +el.dataset.dy * Math.min(1, css / 0.72);
      el.style.setProperty("--ax", `${x.toFixed(1)}px`);
      el.style.setProperty("--ay", `${y.toFixed(1)}px`);
      el.style.setProperty("--dy", `${dy.toFixed(1)}px`);
    });
  }
  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const r = canvas.getBoundingClientRect();
    vw = Math.max(1, r.width); vh = Math.max(1, r.height);
    renderer.setPixelRatio(dpr);
    renderer.setSize(vw, vh, false);
    const narrow = vw < 760;
    const vis = (el) => el && el.offsetParent !== null && getComputedStyle(el).display !== "none";
    const copy = hero.querySelector(".hero h1").getBoundingClientRect();   // the headline, behind the picture
    hero.style.setProperty("--copy-b", `${Math.round(copy.bottom - r.top)}px`);   // the side columns start below the headline
    const foot = hero.querySelector(".hero__foot").getBoundingClientRect();
    const left = $("hx-left"), right = $("hx-right");
    const boxL = vis(left) ? left.getBoundingClientRect().right - r.left + 8 : 12;
    const boxR = vis(right) ? right.getBoundingClientRect().left - r.left - 8 : vw - 12;
    const boxT = copy.bottom - r.top - copy.height * (narrow ? 0.16 : 0.22);   // the valley covers the headline's lower part
    const boxB = vh;                                                            // ...and its foot meets the bottom of the hero
    const visW = VIS.x1 - VIS.x0, visH = VIS.y1 - VIS.y0;
    css = narrow ? Math.min((boxB - boxT) / visH, vw / 640) : Math.min((boxB - boxT) / visH, (vw * 0.98) / visW);
    css = Math.max(css, 0.2);
    scale = css * dpr;
    const cx = narrow ? VALLEY_X : (VIS.x0 + VIS.x1) / 2;
    const midX = vw / 2;
    void foot; void boxL; void boxR;
    offX = (midX - cx * css) * dpr;
    offY = (boxT - (VIS.y0 - P.head.top) * css) * dpr;                         // top of the picture at the box top
    U.uRes.value.set(vw * dpr, vh * dpr);
    U.uOffset.value.set(offX, offY);
    U.uScale.value = scale;
    U.uDpr.value = dpr;
    placeCallouts();
    debug.fit = { css: +css.toFixed(3), box: [boxL, boxT, boxR, boxB].map(Math.round) };
  }
  resize();
  new ResizeObserver(resize).observe(canvas);
  document.fonts?.ready.then(resize);

  // pointer → picture pixels (a finger works the same way on the iPad)
  const mouse = { x: -9999, y: -9999, tx: -9999, ty: -9999, last: -1e9, on: 0 };
  const toPic = (cx, cy) => {
    const r = canvas.getBoundingClientRect();
    return [((cx - r.left) * dpr - offX) / scale, ((cy - r.top) * dpr - offY) / scale + P.head.top];
  };
  const onMove = (e) => {
    const [x, y] = toPic(e.clientX, e.clientY);
    mouse.tx = x; mouse.ty = y; mouse.last = performance.now();
    if (mouse.x < -9000) { mouse.x = x; mouse.y = y; }
  };
  hero.addEventListener("pointermove", onMove, { passive: true });
  hero.addEventListener("pointerdown", onMove, { passive: true });
  hero.addEventListener("pointerleave", () => { mouse.last = performance.now() - 5000; });

  // mode switch: shows the current view; a click jumps to the other and pauses the cycle for a while
  const modeEl = $("mode");
  let cycleT0 = performance.now() / 1000, manual = null, manualUntil = 0;
  modeEl?.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
    manual = b.dataset.mode === "detail" ? 1 : 0;
    manualUntil = performance.now() / 1000 + 9;
  }));

  let mix = still ? 1 : 0, visible = true;
  const period = HOLD_DETAIL + HOLD_WIRE + 2 * TRAVEL;
  function targetMix(t) {
    if (manual != null) {
      if (t < manualUntil) return manual;
      cycleT0 = t - (manual ? TRAVEL : TRAVEL * 2 + HOLD_DETAIL);  // carry on from where the visitor left it
      manual = null;
    }
    if (still) return 1;
    const k = (t - cycleT0) % period;
    if (k < TRAVEL) return ease(k / TRAVEL);                        // wireframe → detail
    if (k < TRAVEL + HOLD_DETAIL) return 1;
    if (k < 2 * TRAVEL + HOLD_DETAIL) return 1 - ease((k - TRAVEL - HOLD_DETAIL) / TRAVEL);
    return 0;
  }
  const io = new IntersectionObserver(([en]) => { visible = en.isIntersecting; if (visible) loop(); });
  io.observe(hero);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) loop(); });

  let lastT = performance.now() / 1000, raf = 0;
  function frame() {
    raf = 0;
    if (!visible || document.hidden) return;
    const now = performance.now();
    const t = now / 1000, dt = Math.min(0.05, t - lastT); lastT = t;
    const goal = targetMix(t);
    mix += (goal - mix) * (manual != null ? Math.min(1, dt * 2.2) : 1);
    // the nudge follows a real pointer only, and fades out a moment after it stops or leaves
    const idle = now - mouse.last > 1200;
    mouse.x += (mouse.tx - mouse.x) * Math.min(1, dt * 10);
    mouse.y += (mouse.ty - mouse.y) * Math.min(1, dt * 10);
    const want = mouse.tx > -9000 && !idle ? 1 : 0;
    mouse.on += (want - mouse.on) * Math.min(1, dt * 5);
    U.uTime.value = t; U.uMix.value = mix; U.uHover.value = mouse.on;
    U.uMouse.value.set(mouse.x, mouse.y);
    renderer.render(scene, cam);
    const mode = mix > 0.5 ? "detail" : "wire";
    if (mode !== debug.mode) {
      debug.mode = mode;
      modeEl?.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === mode)));
    }
    debug.frames++; debug.mix = mix;
    raf = requestAnimationFrame(frame);
  }
  function loop() {
    if (!raf && visible && !document.hidden) { lastT = performance.now() / 1000; raf = requestAnimationFrame(frame); }
  }
  hero.classList.add("is-ready");
  debug.ready = true;
  loop();
}

// ---------- scroll: word-by-word statement, fade-ups, step dots ----------
function wordReveal() {
  const el = $("statement");
  if (!el) return;
  const words = [];
  const walk = (node) => {
    [...node.childNodes].forEach((ch) => {
      if (ch.nodeType === 3) {
        const frag = document.createDocumentFragment();
        ch.textContent.split(/(\s+)/).forEach((part) => {
          if (!part) return;
          if (/^\s+$/.test(part)) { frag.append(part); return; }
          const s = document.createElement("span"); s.className = "w"; s.textContent = part;
          frag.append(s); words.push(s);
        });
        ch.replaceWith(frag);
      } else if (ch.nodeType === 1) walk(ch);
    });
  };
  walk(el);
  if (still) { words.forEach((w) => w.classList.add("on")); return; }
  const update = () => {
    const r = el.getBoundingClientRect();
    const p = clamp01((innerHeight * 0.88 - r.top) / (r.height + innerHeight * 0.3));
    const k = Math.round(p * words.length * 1.15);
    words.forEach((w, i) => w.classList.toggle("on", i < k));
  };
  addEventListener("scroll", update, { passive: true });
  addEventListener("resize", update);
  update();
}

function fadeUps() {
  const els = document.querySelectorAll("[data-up]");
  if (still || !("IntersectionObserver" in window)) { els.forEach((e) => e.classList.add("in")); return; }
  const io = new IntersectionObserver((ens) => ens.forEach((en) => {
    if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
  }), { rootMargin: "0px 0px -10% 0px" });
  els.forEach((e) => io.observe(e));
}

function stepDots() {
  const cards = [...document.querySelectorAll(".stack__card")];
  const dots = [...document.querySelectorAll(".stack__dots i")];
  if (!cards.length || !dots.length) return;
  const update = () => {
    let k = 0;
    cards.forEach((c, i) => { if (c.getBoundingClientRect().top < innerHeight * 0.55) k = i; });
    dots.forEach((d, i) => d.classList.toggle("on", i === k));
  };
  addEventListener("scroll", update, { passive: true });
  update();
}

fillNumbers();
wordReveal();
fadeUps();
stepDots();
startHero().catch((e) => {
  debug.error = String((e && e.message) || e);
  $("hero")?.classList.add("no-gl");
});
