// About and Drone data sections on the home page (ticket style, Typhon v2 palette, the lead's fonts).
// Numbers come from the running app (spec.json); anything missing says "not measured" instead of guessing.
import "@fontsource/space-grotesk/latin-600.css";
import "@fontsource/space-grotesk/latin-700.css";
import "@fontsource/inter/latin-600.css";
import "./styles/zine.css";
import { api } from "./api.js";
import { num } from "./format.js";

const set = (key, text) => document.querySelectorAll(`[data-fact="${key}"]`).forEach((el) => { el.textContent = text; });

(async () => {
  if (!document.querySelector("[data-fact]")) return;
  let spec = null;
  try { spec = await api.spec(); } catch { /* facts stay "not measured" */ }
  const a = spec?.accuracy, t = spec?.timing;
  if (a?.horizontal?.rmse_h_m != null) {
    set("rmse_h", `±${num(a.horizontal.rmse_h_m, "", 1)} m`);
    set("n_checkpoints", String(a.n_checkpoints));
  }
  if (a?.vertical_relative?.std_m != null) set("rel_v", `±${num(a.vertical_relative.std_m, "", 1)} m`);
  if (t?.minutes_per_ha != null) {
    set("min_per_ha", num(t.minutes_per_ha, "", 1));
    set("area_ha", num(t.area_ha, "", 1));
    set("total_min", num(t.total_minutes, "", 0));
  }
})();
