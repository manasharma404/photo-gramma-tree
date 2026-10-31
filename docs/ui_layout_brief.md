# UI layout brief (for the lead's design)

**What this is:** everything the interface has to show and do, where the data comes from, and the meanings that must stay visible. **What it isn't:** a visual design. Boxes below are only for *where things could go*; layout, colour, type, icons and style are the lead's decisions. Anything you'd arrange differently, change it; tell Claude and the implementation follows the design.

**Stack (fixed by the brief):** a web app served offline by our laptop (`api/`), MapLibre for the 2D map, three.js for 3D. Everything bundled locally: fonts, icons and libraries can't load from the internet at runtime.

**Audiences:**
1. **Laptop dashboard** (command post; also what goes on the PPT slides).
2. **Phone** over the laptop's hotspot (field team; judges in later rounds).
3. **Printable PDF map** (the teammate's export; it should echo the dashboard's legend).

---

## 1. Meanings that must be visible (the design decides how)

| Meaning | Where it appears | Rule from the brief / our data |
|---|---|---|
| Road status: **open / partial / blocked / unknown** | map, lists, cards | Different **shape or pattern**, not only colour (blocked: solid with ✕; unknown: grey hatching, per brief). Must survive black-and-white printing |
| **Needs verification** | road detail, act-now cards | Flag from the assessment engine |
| **Source of a status**: measured (drone) / field report (phone) / scenario (from reports) | road detail, legend | Field reports override geometry; scenario = Wayanad |
| **Measured vs estimate vs placeholder** | every number | Each number shows its tolerance (e.g. "4.2 m ± 0.3 m"), or "ESTIMATE", or "PLACEHOLDER" |
| **Not measured yet** | any missing value | Never a dash that looks like zero; never a guess |
| **Data label**: "USGS public data, not our footage" / "Our footage (DJI Neo 2)" / "Scenario reconstructed from reports, not drone-measured" | site switcher, map corner, exports | Hard rule 6 |
| **Offline** | top bar | From `GET /health` (truthful: "No internet: running locally") |
| **Data freshness** | top bar or footer | Survey time, processing time, number of field reports |
| **Decision support, not dispatch** | priorities | Wording rule; weights are hand-set (PLACEHOLDER), never "AI" |

---

## 2. Laptop dashboard

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ A. TOP BAR: site switcher · data label · vehicle switch · freshness · offline │
├───────────────────────────────────────────────┬───────────────────────────────┤
│ B. MAP  (or 3D, or split)                      │ C. SIDE PANEL (tabs)          │
│                                               │  1 Act now                    │
│   orthophoto + roads by status + places        │  2 Roads                      │
│   + measurements + checkpoints + reports       │  3 Measure                    │
│                                               │  4 Accuracy & spec            │
│  [D. tools]           [legend] [scale] [N]    │  5 Field reports              │
│                                     [2D|3D]   │                               │
├───────────────────────────────────────────────┴───────────────────────────────┤
│ E. STATUS STRIP (optional): coordinates under cursor · CRS · active run id     │
└───────────────────────────────────────────────────────────────────────────────┘
```

### A. Top bar
| Element | Content | Data |
|---|---|---|
| Site switcher | South Fork (USGS) · Wayanad (scenario) · Neo 2 field (ours) | `data/active.json` today; a list endpoint later |
| Data label | text from the table in section 1, always visible | per site |
| Vehicle switch | Fire truck · Ambulance · Jeep · Foot | drives road colours, act-now, reachability |
| Freshness | "Surveyed 30 Apr 2024 · processed 31 Oct 06:40 · 3 field reports" | run.json, field reports |
| Offline badge | "Offline: running on this laptop" | `GET /health` |

### B. Map (MapLibre)
| Layer | What | Data | Notes |
|---|---|---|---|
| Orthophoto | our map, the base | tiles from the run (Claude makes them) | 5 cm pixels; two disconnected pieces on South Fork |
| Height shading | optional toggle: hillshade of DSM | DSM | |
| Survey footprint | outline of where we have data | orthophoto valid area | outside = no data |
| Roads | status **for the selected vehicle** | `GET /advisor/state` + `segments.geojson` | 4 statuses + "needs verification" |
| Places | settlements, shelters (campground), landing-zone candidates | `places.geojson` | cut-off places for the selected vehicle highlighted |
| Measurements | drawn results: span line + bank points, volume polygon, LZ squares + approach rays, working-space rectangle | `measurement.json` results | |
| Checkpoints | surveyed target + where our map put it + error arrow | `accuracy.json` | arrows are the honest story (35 m on the single strip) |
| Field reports | pins from phones | `/advisor/state` (source field_report) | |
| Uncovered/unknown | areas we couldn't see (canopy, vegetation) | from road coverage; later teammate's T14 | hatch, per the "unknown" meaning |
| Map furniture | legend, scale bar, north arrow, attribution "© OpenStreetMap contributors; imagery USGS (public domain)" | | attribution is a licence requirement |

### C. Side panel tabs
1. **Act now:** ranked cards. Card = title (what to do), place, the 2–3 numbers that justify it, status chip, "why" (reasons list), "needs verification" flag, "decision support" wording. Data: `GET /advisor/priorities` + `access_report.reopen_plan`.
2. **Roads:** filter by status for the selected vehicle; list rows → **segment detail**: length, corridor width (and whether it's OSM or a default), clear width ± tol, max obstruction ± tol, obstructed length, debris volume ± tol, coverage %, status for all 4 vehicles with reasons, source, needs-verification.
3. **Measure:** the four tools and their results.
   - **Span** (draw a line across a gap): span ± tol, bank heights, bed height, **profile chart** (we already render a PNG; could be a live chart), Bailey panel estimate (PLACEHOLDER rule).
   - **Debris volume** (draw a polygon): volume ± tol, area, max height, reference surface.
   - **Landing zones** (pick helicopter type): up to 5 candidates, each with FATO size, max slope, obstacle in safety ring, approach directions clear, **"approach runs beyond our map" warning**.
   - **Working space** (click a point; required size): rectangle size vs requirement, meets yes/no.
   Every result lists the placeholders it used.
4. **Accuracy & spec:** the spec card: "±X m horizontal / ±Y m vertical at N checkpoints (method)", processing time, area, minutes per hectare, laptop specs, validation table, data sources. Missing → "not measured yet". The single-strip lesson ("one flight line → 35 m sideways error") can live here as a finding.
5. **Field reports:** list with time, segment, kind, note, vehicle; click → map.

### D. Map tools
Draw line (span) · draw polygon (volume) · click point (working space) · LZ search · clear · 2D/3D toggle. Drawing gives immediate visual feedback; the result appears in tab 3.

---

## 3. 3D view (three.js)

| Element | What | Data |
|---|---|---|
| Terrain | mesh from the DSM with the orthophoto draped on it | DSM + orthophoto (Claude exports a lighter mesh/heightmap per run) |
| Vertical exaggeration | slider (1× … 3×), with a visible "×N" label | |
| Roads in 3D | draped lines with the same status vocabulary as 2D | same as map |
| Measurements in 3D | span line between bank tops + bed point; volume polygon as a lifted outline; LZ squares with 8 approach rays (clear vs blocked); working-space rectangle | measurement results |
| Camera | orbit, reset, compass, top-down preset | |
| Click to measure | optional: pick on the mesh → same API calls as 2D | `/measure/*` |
| Honesty note | "Heights relative to surroundings; absolute height ± Y m" (from accuracy) | accuracy.json |

**Your calls:** 3D as a full-screen toggle, a split with the map, or a modal for a selected measurement? What it opens on (whole site, or the selected segment/measurement)?

---

## 4. Phone

```
┌──────────────────────┐
│ site · offline · veh │  compact top bar
│                      │
│        MAP           │  full screen
│                      │
├──────────────────────┤
│ ▲ bottom sheet        │  tabs: Act now · Roads · Report
└──────────────────────┘
```
- **Report** = the teammate's `/field` page (already working: pick where you are → dead end / cleared / new debris / other). Needs the lead's styling; its content stays.
- No drawing tools on phone (laptop-only), but results are viewable.
- Big touch targets; readable in sunlight.

---

## 5. States every component needs
Loading · **no active run** ("No map processed yet") · empty (e.g. no field reports) · offline API error · "not measured yet" · **mock data** badge (while building against `contracts/examples/`) · stale data (field report newer than survey).

---

## 6. What Claude needs from the lead
1. **Design tokens:** colours (incl. the 4 statuses + needs-verification), type scale, spacing, radii. As a list or a Figma style export.
2. **Frames** for: laptop dashboard (each tab once), 3D view, phone (map + sheet + report), one card and one segment detail at full detail.
3. **Status symbols:** line styles/patterns/icons for open / partial / blocked / unknown, and markers for places, LZs, checkpoints, field reports.
4. Decisions: 3D placement (section 3), default site and vehicle, tab order.

## 7. What Claude can build now without taking any visual decision
The plumbing behind every box above, in neutral grey so your styles drop in through tokens:
- orthophoto **tiles** and a **3D terrain mesh** per run
- the data loaders for every layer and tab (against contract mocks, then live)
- the measure tools' drawing → API → result flow
- MapLibre and three.js bundled locally (offline)
- 2D ↔ 3D switching

Nothing in that grey version is a design proposal; it gets restyled to your frames.
