// Thin wrappers over the offline API (api/main.py). A failed call returns null and records why,
// so the UI can show "not measured yet" / "not available" instead of breaking.
//
// Snapshot mode (built with `npm run build:snapshot`): the same UI reads saved JSON files
// (scripts/make_snapshot.py) instead of the live server, so it can be hosted anywhere as static files.
// Measuring needs the live server, so it reports that instead of computing.
export const lastErrors = {};
export const SNAPSHOT = import.meta.env.VITE_SNAPSHOT === "1";
// site root: "./" on the landing page, "../" on /app/ (set by a <meta name="typhon-root"> in each page)
const ROOT = new URL(document.querySelector('meta[name="typhon-root"]')?.content || "./", location.href).href;

export async function getJSON(url) {
  try {
    const r = await fetch(url);
    if (!r.ok) {
      lastErrors[url] = `${r.status} ${(await r.text()).slice(0, 200)}`;
      return null;
    }
    return await r.json();
  } catch (e) {
    lastErrors[url] = String(e);
    return null;
  }
}

export async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : `HTTP ${r.status}`);
  return data;
}

// in a snapshot, tile/terrain URLs are stored root-relative; make them absolute for MapLibre/three.js
const rooted = (u) => (u ? ROOT + u.replace(/^\//, "") : u);
const snap = (name) => getJSON(`${ROOT}data/${name}.json`);

const live = {
  health: () => getJSON("/health"),
  active: () => getJSON("/accuracy/active"),
  spec: () => getJSON("/accuracy/spec"),
  layer: (name) => getJSON(`/accuracy/layers/${name}`),
  state: (p) => getJSON(`/advisor/state?project=${encodeURIComponent(p)}`),
  priorities: (p) => getJSON(`/advisor/priorities?project=${encodeURIComponent(p)}`),
  access: (p) => getJSON(`/advisor/access?project=${encodeURIComponent(p)}`),
  reports: (p) => getJSON(`/advisor/reports?project=${encodeURIComponent(p)}`),
  helicopters: () => getJSON("/measure/helicopters"),
  measure: (kind, body) => postJSON(`/measure/${kind}`, body),
};

const snapshot = {
  health: () => snap("health"),
  active: async () => {
    const a = await snap("active");
    if (a?.tiles) a.tiles.url = rooted(a.tiles.url);
    if (a?.terrain) a.terrain.url = rooted(a.terrain.url);
    return a;
  },
  spec: () => snap("spec"),
  layer: (name) => snap(`layers/${name}`),
  state: () => snap("advisor/state"),
  priorities: () => snap("advisor/priorities"),
  access: () => snap("advisor/access"),
  reports: () => snap("advisor/reports"),
  helicopters: () => snap("helicopters"),
  measure: async () => {
    throw new Error("measuring runs on the Typhon laptop; this is a read-only snapshot");
  },
};

export const api = SNAPSHOT ? snapshot : live;
