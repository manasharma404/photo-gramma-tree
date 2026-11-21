// Field outbox (finale item 4): a report made with no signal is kept on this phone and sent by itself when the
// laptop is reachable again. Also adds "Save the map to this phone" (the latest map as a PDF that opens offline).
//
// Honest limits, also shown on the page: the outbox lives in this browser on this phone and only empties while the
// page is open; phones reach the laptop over plain http, so the page itself cannot be reopened with no signal
// (browsers only allow that over https). Each kept report carries the time it was observed.
(function () {
  "use strict";
  const KEY = "typhon_outbox_v1";
  const RETRY_MS = 10000;

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch (_) { return []; }
  }
  function save(items) {
    try { localStorage.setItem(KEY, JSON.stringify(items)); } catch (_) {}
    render();
  }
  function hhmm(d) {
    return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  }

  // keep a report that could not be sent; returns how many are now waiting
  function keep(payload, headers) {
    const now = new Date();
    const stamp = "[observed " + hhmm(now) + ", sent later from the phone outbox]";
    const p = Object.assign({}, payload);
    p.note = ((p.note ? p.note + " " : "") + stamp).slice(0, 500);
    const items = load();
    items.push({ payload: p, headers: headers || {}, kept_at: now.toISOString() });
    save(items);
    return items.length;
  }

  let sending = false;
  async function flush() {
    const items = load();
    if (!items.length || sending) return;
    sending = true;
    try {
      while (items.length) {
        const it = items[0];
        let r;
        try {
          r = await fetch("/advisor/reports", {
            method: "POST",
            headers: Object.assign({ "Content-Type": "application/json" }, it.headers),
            body: JSON.stringify(it.payload),
          });
        } catch (_) {
          break; // still no signal: try again later
        }
        if (r.status === 401) { setMsg("Sign in again to send the reports kept on this phone."); break; }
        if (r.status === 429) break; // locked out for now: try later
        items.shift(); // sent (2xx), or refused for good (for example an unknown road): never resend forever
        save(items);
        if (!r.ok) {
          const d = await r.json().catch(function () { return {}; });
          setMsg("A kept report was refused by the laptop: " + (d.detail || ("HTTP " + r.status)));
        } else {
          setMsg("Sent a report kept on this phone.");
        }
      }
    } finally {
      sending = false;
      render();
    }
  }

  // ---------- on the page ----------
  let bar, msg;
  function setMsg(t) { if (msg) msg.textContent = t || ""; }
  function render() {
    if (!bar) return;
    const n = load().length;
    bar.hidden = n === 0;
    bar.querySelector("b").textContent = n === 1 ? "1 report is waiting" : n + " reports are waiting";
  }
  function mount() {
    const anchor = document.getElementById("toast");
    bar = document.createElement("div");
    bar.className = "outbox";
    bar.setAttribute("role", "status");
    bar.innerHTML = "<b></b> on this phone. They send by themselves when you are back in range of the laptop. Keep this page open.";
    msg = document.createElement("p");
    msg.className = "outbox__msg";
    if (anchor) { anchor.after(bar); bar.after(msg); } else { document.body.prepend(bar); }

    // Save the map to this phone (a PDF; opens with no signal)
    const sel = document.getElementById("project-select");
    const card = sel ? sel.closest(".card") : null;
    if (card) {
      const a = document.createElement("a");
      a.className = "outbox__save";
      a.textContent = "Save the map to this phone (PDF, opens with no signal)";
      a.href = "#";
      a.addEventListener("click", function (e) {
        e.preventDefault();
        const p = sel.value ? "?project=" + encodeURIComponent(sel.value) : "";
        a.textContent = "Preparing the latest map… (can take about 30 s)";
        window.location.href = "/field/map.pdf" + p;
        setTimeout(function () { a.textContent = "Save the map to this phone (PDF, opens with no signal)"; }, 30000);
      });
      card.appendChild(a);
    }
    render();
  }

  window.TyphonOutbox = { keep: keep, flush: flush, count: function () { return load().length; } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount); else mount();
  window.addEventListener("online", flush);
  setInterval(flush, RETRY_MS);
  setTimeout(flush, 1500);
})();
