import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/space-grotesk/latin-300.css";
import "@fontsource/space-grotesk/latin-400.css";
import "@fontsource/space-grotesk/latin-500.css";
import "./styles/tokens.css";
import "./styles/landing.css";
import { SNAPSHOT, api } from "./api.js";
import { mountIcons } from "./icons.js";
import { num } from "./format.js";

mountIcons();

// The field form needs the Typhon laptop; in the public read-only snapshot it's a label, not a dead link.
if (SNAPSHOT) document.querySelectorAll('a[href="field"]').forEach((a) => {
  a.removeAttribute("href");
  a.title = "Field reports run on the Typhon laptop";
});

// Facts come from the running app (spec.json); anything missing says so instead of guessing.
(async () => {
  if (!document.getElementById("facts")) return; // the About page now lives at about/
  const spec = await api.spec();
  const a = spec?.accuracy, t = spec?.timing;
  const fact = (value, label) => `<div class="fact"><b>${value}</b><span>${label}</span></div>`;
  document.getElementById("facts").innerHTML =
    fact("0", "internet connections needed at runtime")
    + fact("0", "ground control points used to build the map")
    + fact(t?.minutes_per_ha != null ? num(t.minutes_per_ha, "", 1) : "—",
      t?.minutes_per_ha != null ? "minutes per hectare on one laptop (measured)" : "minutes per hectare: not measured yet")
    + fact(a ? `±${num(a.horizontal.rmse_h_m, "", 1)} m` : "—",
      a ? `horizontal error at ${a.n_checkpoints} surveyed checkpoints (latest run)` : "accuracy: not measured yet");
})();
