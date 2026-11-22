// Home page v7 (22 Nov): the hero is a concept valley drawn like a relief-printed survey sheet, as a small game board
// (hero3d.js). It is an illustration made in code, not map data, and says so. The measured numbers further down come
// from story_anchors.json (scripts/bake_story_anchors.py, from the run files); none is typed in here.
import "@fontsource/inter/latin-300.css";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/space-grotesk/latin-500.css";
import "@fontsource/space-grotesk/latin-600.css";
import "./styles/tokens.css";
import "./styles/story.css";
import { mountIcons } from "./icons.js";
import { createHero } from "./hero3d.js";
import anchors from "./assets/story_anchors.json";

mountIcons();
const $ = (id) => document.getElementById(id);
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
const debug = (window.__story = { frames: 0, ready: false, error: null });
const clamp01 = (v) => Math.min(1, Math.max(0, v));

// ---------- measured numbers (from the run files, via story_anchors.json) ----------
function fillNumbers() {
  const m = anchors.numbers?.map || {};
  const ph = anchors.numbers?.photos || {};
  const f = (v, d = 1) => (v == null ? "PENDING" : Number(v).toFixed(d));
  const vals = { minutes: f(m.minutes), area: f(m.area_ha, 2), photos: m.photos ?? "PENDING", rmse: f(m.rmse_h_m, 2),
    ncp: m.n_checkpoints ?? "PENDING", arrival: f(ph.arrival_to_map_s_typical, 1), worst: f(ph.arrival_to_map_s_worst, 1) };
  document.querySelectorAll("[data-num]").forEach((el) => { el.textContent = vals[el.dataset.num] ?? "PENDING"; });
}

// ---------- the board ----------
const ANSWERS = {
  truck: "<b>Fire truck:</b> stops at the debris. The village is cut off: clear this road first.",
  ambulance: "<b>Ambulance:</b> stops at the debris. The village is cut off: clear this road first.",
  jeep: "<b>Jeep:</b> stops at the debris. The village is cut off: clear this road first.",
  foot: "<b>On foot:</b> reaches the village by the trail over the saddle, about an hour longer.",
};
function startBoard() {
  const canvas = $("hero-canvas"), board = canvas.closest(".board");
  const pins = new Map([...document.querySelectorAll("[data-pin]")].map((el) => [el.dataset.pin, el]));
  let hero;
  try {
    hero = createHero(canvas, {
      still,
      onPins: (list) => {
        for (const p of list) {
          const el = pins.get(p.id); if (!el) continue;
          el.style.transform = `translate(${p.x.toFixed(1)}px, ${p.y.toFixed(1)}px)`;
          el.style.visibility = p.on ? "visible" : "hidden";
        }
        debug.frames++;
      },
    });
  } catch (e) {
    debug.error = "webgl: " + (e && e.message);
    board.classList.add("no-gl");
    return;
  }
  board.classList.add("is-ready");
  debug.ready = true;

  // "what it answers" chips light up their pins
  const chips = [...document.querySelectorAll("#chips button")];
  chips.forEach((b) => b.addEventListener("click", () => {
    const on = !b.classList.contains("on");
    chips.forEach((c) => c.classList.toggle("on", c === b && on));
    board.classList.toggle("focus", on);
    pins.forEach((el, id) => el.classList.toggle("hot", on && id === b.dataset.kind));
  }));
  // vehicle picker: vehicles stop at the blockage, on foot takes the trail
  const veh = [...document.querySelectorAll("#veh button")];
  veh.forEach((b) => b.addEventListener("click", () => {
    veh.forEach((c) => c.setAttribute("aria-pressed", String(c === b)));
    hero.setMode(b.dataset.mode);
    $("answer").innerHTML = ANSWERS[b.dataset.mode];
  }));
  document.querySelectorAll(".zoom button").forEach((b) => b.addEventListener("click", () => hero.zoomBy(b.dataset.z === "in" ? 0.85 : 1.18)));
  $("preview").addEventListener("click", () => {
    veh.find((c) => c.dataset.mode === "foot")?.click();
    hero.preview();
  });
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
try { startBoard(); } catch (e) { debug.error = String((e && e.message) || e); }
