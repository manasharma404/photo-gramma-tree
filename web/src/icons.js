// Line icons in the brand style (stroke, rounded). Inline SVG: nothing loads from the internet.
const svg = (d, size = 22) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;

export const ICONS = {
  act: svg('<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>'),
  roads: svg('<path d="M8 3 5 21M16 3l3 18M12 4v3M12 10v3M12 16v3"/>'),
  measure: svg('<path d="M3 17 17 3l4 4L7 21z"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2"/>'),
  accuracy: svg('<circle cx="12" cy="12" r="8"/><path d="M12 4v4M12 16v4M4 12h4M16 12h4"/>'),
  reports: svg('<path d="M6 3h9l4 4v14H6z"/><path d="M14 3v5h5M9 13h7M9 17h5"/>'),
  layers: svg('<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>'),
  cursor: svg('<path d="M5 3l14 7-6 2-2 6z"/>'),
  line: svg('<circle cx="5" cy="18" r="2"/><circle cx="19" cy="6" r="2"/><path d="M6.5 16.5 17.5 7.5"/>'),
  polygon: svg('<path d="M5 6l9-2 6 7-4 9-10-3z"/>'),
  point: svg('<path d="M12 21s7-6.5 7-12a7 7 0 0 0-14 0c0 5.5 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>'),
  landing: svg('<circle cx="12" cy="12" r="9"/><path d="M9 8v8M15 8v8M9 12h6"/>'),
  trash: svg('<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>'),
  cube: svg('<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/>'),
  alert: svg('<path d="M12 3 2 20h20z"/><path d="M12 10v4M12 17v.5"/>'),
  chevron: svg('<path d="m9 6 6 6-6 6"/>', 18),
  close: svg('<path d="M6 6l12 12M18 6 6 18"/>', 18),
  arrow: svg('<path d="M5 12h14M13 6l6 6-6 6"/>', 18),
  expand: svg('<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>', 18),
  mountain: svg('<path d="M2 18c3-1 5-6 8-9 2 2 3 4 5 4 2-2 3-3 4-3l3 8"/><path d="M6 18c2-2 4-3 6-3"/>', 28),
  export: svg('<path d="M12 3v12M7 8l5-5 5 5M5 15v5h14v-5"/>'),
};

export function mountIcons(root = document) {
  root.querySelectorAll("[data-icon]").forEach((el) => {
    if (!el.dataset.iconMounted) {
      el.insertAdjacentHTML("afterbegin", ICONS[el.dataset.icon] || "");
      el.dataset.iconMounted = "1";
    }
  });
}
