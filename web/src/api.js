// Thin wrappers over the offline API (api/main.py). A failed call returns null and records why,
// so the UI can show "not measured yet" / "not available" instead of breaking.
export const lastErrors = {};

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

export const api = {
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
