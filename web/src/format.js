// Number formatting with honesty rules: missing -> "not measured yet", tolerance shown when known.
export const NOT_MEASURED = '<span class="not-measured">not measured yet</span>';

export function num(v, unit = "", digits = 1) {
  if (v === null || v === undefined || Number.isNaN(v)) return NOT_MEASURED;
  return `${Number(v).toFixed(digits)}${unit ? " " + unit : ""}`;
}

export function withTol(v, tol, unit, digits = 1) {
  if (v === null || v === undefined) return NOT_MEASURED;
  return tol === null || tol === undefined ? `${num(v, unit, digits)} <span class="muted">(± not measured yet)</span>`
    : `${num(v, unit, digits)} ± ${num(tol, unit, digits)}`;
}

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export const VEHICLES = [
  ["fire_truck", "Fire truck"], ["ambulance", "Ambulance"], ["jeep", "Jeep"], ["foot", "Foot"],
];
export const STATUSES = ["open", "partial", "blocked", "unknown"];

export function chip(status) {
  return `<span class="chip chip--${esc(status)}">${esc(status)}</span>`;
}
