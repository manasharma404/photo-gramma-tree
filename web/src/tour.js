// Guided tour of the dashboard: a spotlight on one part at a time, with Back / Next / Skip.
// Runs once on the first visit (remembered in this browser only) and again from the "Guide" button.
import { SNAPSHOT } from "./api.js";
import { showTab } from "./panel.js";

const KEY = "typhon-tour-done-v1";
const $ = (id) => document.getElementById(id);

function steps(spec) {
  const acc = spec?.accuracy;
  const err = acc?.horizontal?.rmse_h_m != null
    ? `Here the map is off by about ±${acc.horizontal.rmse_h_m.toFixed(1)} m, measured at ${acc.n_checkpoints} surveyed checkpoints.`
    : "The error hasn't been measured for this map yet, and the dashboard says so.";
  return [
    { title: "Welcome to Typhon", text: "The first map after a landslide: made from drone photos, on one laptop, with no internet. This tour shows the important parts, one at a time. It takes about a minute." },
    { target: "#site", title: "Which map you're looking at", text: "The survey on screen. Right now that's USGS public photos of a real debris flow in South Fork, California, processed by us. It's not our own footage, and the page says so." },
    { target: "#vehicle", title: "Pick who is going", text: "Fire truck, ambulance, jeep or a team on foot. Every road colour, count and warning updates for the vehicle you pick." },
    { target: "#legend", title: "How to read the roads", text: "Solid green: open. Dashed amber: partly blocked. Red with ✕: blocked. Grey dotted: unknown, meaning we couldn't see it. Unknown is never shown as open." },
    { target: "#map", title: "The map", text: "The drone map with roads, places and checkpoints on top. Click a road to see why it has its status. Scroll to zoom." },
    { target: "#panel", tab: "act", title: "Start here: Act now", text: "What needs attention first: blocked roads, places cut off or with access unverified, and how far the map can be trusted. The priority list uses hand-set weights: it's decision support, not dispatch." },
    { target: "#tools", tab: "measure", title: "Measure tools",
      text: "Draw across a gap to get its span and height profile, outline a debris pile for its volume, or check a landing zone. Every result comes with its error."
        + (SNAPSHOT ? " (Measuring runs on the Typhon laptop; this public copy is read-only.)" : "") },
    { target: '[data-tab="accuracy"]', tab: "accuracy", title: "How far off is the map?", text: `${err} We show this next to every measurement instead of hiding it.` },
    { target: "#card-3d", title: "3D view", text: "The terrain model built from the same photos. Open it to look along a slope or a gap." },
    { target: '[data-tab="reports"]', tab: "reports", title: "Field reports", text: "Teams on the ground send what they see from a phone (\"road blocked\", \"cleared\"), and it overrides what the map guessed."
        + (SNAPSHOT ? " (Phones connect to the Typhon laptop; this public copy is read-only.)" : "") },
    { target: "#offline", title: "No internet needed", text: "Everything runs on this laptop. This badge shows whether the machine is online, but nothing depends on it." },
    { title: "You're set", text: "Pick a vehicle and start with Act now. Replay this tour any time with the Guide button at the top.", tabAfter: "act" },
  ];
}

function visible(el) {
  if (!el) return false;
  const r = el.getBoundingClientRect();
  return r.width > 4 && r.height > 4 && getComputedStyle(el).visibility !== "hidden";
}

export function initTour(getSpec) {
  const btn = document.createElement("button");
  btn.className = "pill tour-btn";
  btn.type = "button";
  btn.innerHTML = '<span aria-hidden="true">?</span> Guide';
  btn.addEventListener("click", () => start(getSpec()));
  document.querySelector(".topbar")?.append(btn);

  let done = false;
  try { done = localStorage.getItem(KEY) === "1"; } catch { /* storage blocked: still offer the tour */ }
  // automated checks (navigator.webdriver) open it with the button instead, so it never covers what they click
  if (!done && !navigator.webdriver) setTimeout(() => start(getSpec()), 600);
}

function start(spec) {
  document.querySelector(".tour")?.remove();
  const list = steps(spec);
  const root = document.createElement("div");
  root.className = "tour";
  root.innerHTML = `<div class="tour__shade"></div><div class="tour__spot"></div>
    <div class="tour__card" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      <p class="tour__count"></p><h2 id="tour-title"></h2><p class="tour__text"></p>
      <div class="tour__dots" aria-hidden="true"></div>
      <div class="tour__actions"><button type="button" class="tour__skip">Skip tour</button>
        <span></span><button type="button" class="tour__back">Back</button><button type="button" class="tour__next">Next</button></div>
    </div>`;
  document.body.append(root);
  const card = root.querySelector(".tour__card"), spot = root.querySelector(".tour__spot");
  let i = 0;

  const finish = () => {
    try { localStorage.setItem(KEY, "1"); } catch { /* fine */ }
    showTab(list[list.length - 1].tabAfter || "act");
    root.remove();
    window.removeEventListener("resize", place);
    document.removeEventListener("keydown", onKey);
  };

  function place() {
    const s = list[i];
    const el = s.target && document.querySelector(s.target);
    const vw = innerWidth, vh = innerHeight, cw = Math.min(360, vw - 24);
    card.style.width = `${cw}px`;
    if (!visible(el)) { // centre card, no spotlight
      spot.style.display = "none";
      root.classList.add("tour--plain");
      card.style.left = `${(vw - cw) / 2}px`;
      card.style.top = `${Math.max(12, (vh - card.offsetHeight) / 2)}px`;
      return;
    }
    root.classList.remove("tour--plain");
    const r = el.getBoundingClientRect(), pad = 6;
    Object.assign(spot.style, { display: "block", left: `${r.left - pad}px`, top: `${r.top - pad}px`, width: `${r.width + pad * 2}px`, height: `${r.height + pad * 2}px` });
    const ch = card.offsetHeight, gap = 14;
    let left, top;
    if (r.height > vh * 0.55 && r.width > vw * 0.45) { left = r.left + 24; top = r.bottom - ch - 24; } // big target: card inside it
    else if (r.bottom + gap + ch < vh) { left = r.left; top = r.bottom + gap; }
    else if (r.top - gap - ch > 0) { left = r.left; top = r.top - gap - ch; }
    else if (r.right + gap + cw < vw) { left = r.right + gap; top = r.top; }
    else { left = r.left - gap - cw; top = r.top; }
    card.style.left = `${Math.min(Math.max(12, left), vw - cw - 12)}px`;
    card.style.top = `${Math.min(Math.max(12, top), vh - ch - 12)}px`;
  }

  function show(n) {
    // skip steps whose target isn't on screen (e.g. phone layout)
    const dir = n >= i ? 1 : -1;
    while (n > 0 && n < list.length - 1 && list[n].target) {
      if (list[n].tab) showTab(list[n].tab);
      if (visible(document.querySelector(list[n].target))) break;
      n += dir;
    }
    i = Math.max(0, Math.min(n, list.length - 1));
    const s = list[i];
    if (s.tab) showTab(s.tab);
    root.querySelector(".tour__count").textContent = `${i + 1} / ${list.length}`;
    root.querySelector("#tour-title").textContent = s.title;
    root.querySelector(".tour__text").textContent = s.text;
    root.querySelector(".tour__dots").innerHTML = list.map((_, k) => `<span class="${k === i ? "on" : ""}"></span>`).join("");
    root.querySelector(".tour__back").disabled = i === 0;
    root.querySelector(".tour__next").textContent = i === list.length - 1 ? "Done" : "Next";
    root.querySelector(".tour__skip").hidden = i === list.length - 1;
    requestAnimationFrame(place);
    root.querySelector(".tour__next").focus({ preventScroll: true });
  }

  function onKey(e) {
    if (e.key === "Escape") finish();
    else if (e.key === "ArrowRight") i === list.length - 1 ? finish() : show(i + 1);
    else if (e.key === "ArrowLeft" && i > 0) show(i - 1);
  }

  root.querySelector(".tour__next").addEventListener("click", () => (i === list.length - 1 ? finish() : show(i + 1)));
  root.querySelector(".tour__back").addEventListener("click", () => show(i - 1));
  root.querySelector(".tour__skip").addEventListener("click", finish);
  root.querySelector(".tour__shade").addEventListener("click", (e) => e.stopPropagation());
  window.addEventListener("resize", place);
  document.addEventListener("keydown", onKey);
  show(0);
}
