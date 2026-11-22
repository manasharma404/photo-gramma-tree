// The growing map (F1): start a replay of a photo set; each photo lands on the map at its solved corners as soon as
// the laptop has placed it (about a second after it "arrives"). The photos are drawn by MapLibre itself, one image
// per photo, under the road lines; after every re-solve their corners move a little, which is expected.
import { getJSON, postJSON } from "./api.js";
import { esc } from "./format.js";

const POLL_MS = 1000;
// hard rule: public data is never presented as our footage
const SOURCE = { southfork_block: "USGS public data, not our footage", rec28_campus: "Our footage" };

export function initLive(map, el) {
  const st = { run: null, shown: new Map(), timer: null, fitted: 0 };
  el.innerHTML = `<header><span>Growing map</span><span class="live__state" id="live-state">idle</span></header>
    <div class="live__row"><select id="live-set" aria-label="Photo set"></select>
      <button class="live__btn" id="live-go">Start flight replay</button></div>
    <div class="live__stats" id="live-stats"></div>
    <div class="live__label">Rough map: about 10 to 20 m, for seeing, not for measuring</div>`;
  const $ = (id) => el.querySelector(`#${id}`);

  Promise.all([getJSON("/live/sets"), getJSON("/live/status")]).then(([sets, s]) => {
    if (!sets?.length) { el.hidden = true; return; }  // nothing to replay on this laptop: no empty panel
    el.hidden = false;
    $("live-set").innerHTML = sets.map((x) => `<option value="${esc(x.name)}">${esc(setLabel(x))}</option>`).join("");
    if (s && s.state !== "idle") {  // a replay already ran or is running: show it, and show which set it is
      if (sets.some((x) => x.name === s.set)) $("live-set").value = s.set;
      follow(s);
    }
  });

  $("live-go").addEventListener("click", async () => {
    const running = st.run && ["running", "finishing"].includes(st.last?.state);
    try {
      if (running) {
        await postJSON("/live/stop", {});
      } else {
        clearPhotos();
        follow(await postJSON("/live/start", { set: $("live-set").value, speed: 1 }));
      }
    } catch (e) {
      $("live-stats").textContent = `Could not start: ${e.message}`;
    }
  });

  function follow(s) {
    st.run = s.run_id;
    st.fitted = 0;
    clearTimeout(st.timer);
    tick();
  }

  async function tick() {
    const [s, fp] = await Promise.all([getJSON("/live/status"), getJSON("/live/footprints")]);
    if (s && fp && fp.run_id === st.run) {
      st.last = s;
      render(s);
      draw(fp.photos);
    }
    if (!s || ["running", "finishing"].includes(s.state)) st.timer = setTimeout(tick, POLL_MS);
    else render(s);
  }

  function render(s) {
    const running = ["running", "finishing"].includes(s.state);
    $("live-state").textContent = { running: "flying", finishing: "tidying up", done: "done", stopped: "stopped", failed: "failed" }[s.state] || s.state;
    $("live-state").dataset.state = s.state;
    $("live-go").textContent = running ? "Stop" : "Start flight replay";
    // keeping pace = photos are not piling up; "work" = laptop seconds each photo needs (photos come 1 s apart)
    const work = s.work_s_per_photo_recent, lag = s.arrival_to_placed_s_recent;
    $("live-stats").innerHTML = s.state === "failed" ? `Failed: ${esc(s.error || "")}`
      : `<b>${s.placed}</b> of ${s.photos_total} photos placed ·
         ${s.behind > 1 ? `<span class="live__behind">falling behind: ${s.behind} waiting</span>` : "keeping pace"}
         <br>Each photo on the map <b>${lag == null ? "–" : lag.toFixed(1)} s</b> after it arrives
         · laptop work <b>${work == null ? "–" : work.toFixed(2)} s</b> per photo
         <br><span class="muted">${esc(SOURCE[s.set] || "")}${SOURCE[s.set] ? " · " : ""}GPS: ${esc(s.gps_source || "")}</span>`;
  }

  function draw(photos) {
    const before = map.getLayer("seg-halo") ? "seg-halo" : undefined;
    for (const p of photos) {
      const id = `live-${p.idx}`;
      const src = map.getSource(id);
      if (src) {
        src.setCoordinates(p.corners);
      } else {
        map.addSource(id, { type: "image", url: `/live/thumb/${st.run}/${p.idx}.jpg`, coordinates: p.corners });
        map.addLayer({ id, type: "raster", source: id, paint: { "raster-fade-duration": 0 } }, before);
        st.shown.set(p.idx, id);
      }
    }
    // follow the flight: frame everything placed so far, at the start and then every 15 photos
    if (photos.length && (st.fitted === 0 || photos.length - st.fitted >= 15)) {
      const xs = photos.flatMap((p) => p.corners.map((c) => c[0])), ys = photos.flatMap((p) => p.corners.map((c) => c[1]));
      map.fitBounds([[Math.min(...xs), Math.min(...ys)], [Math.max(...xs), Math.max(...ys)]], { padding: 80, maxZoom: 18, duration: 800 });
      st.fitted = photos.length;
    }
  }

  function clearPhotos() {
    for (const id of st.shown.values()) {
      if (map.getLayer(id)) map.removeLayer(id);
      if (map.getSource(id)) map.removeSource(id);
    }
    st.shown.clear();
  }
}

function setLabel(s) {
  const names = { southfork_block: "USGS South Fork block (public data)", rec28_campus: "Our test flight, 20 Nov" };
  return `${names[s.name] || s.name} · ${s.photos} photos, ${Math.round(s.seconds / 60)} min`;
}
