# TEAMMATE.md v3: the teammate's scope and plan

**Status: work division DECIDED by the lead, 31 Oct 02:00 IST; revised 02:20.** Rule: everything from her six documents is hers, except where it's clearly more efficient for the lead. The lead keeps R1 (accuracy) and, since 02:20, **T9 road measurements and T10 data panels** (they depend on the lead's DSM and styling, and fit the lead's ODM waiting time). v1 and v2 are in git history. Her agent's prompt: `docs/teammate_prompt.md`.

**Her scope (her six documents):** multi-vehicle accessibility · explainable road blockage assessment · rescue priority engine · offline field usability · automatic flight and image quality assessment · positional accuracy and uncertainty reporting (except the checkpoint validator).

**The split in one line:** the lead's side produces the **map, its measurements and everything on screen** (ODM products, accuracy at checkpoints, road segment measurements, span / volume / landing zones / working space, exports, all of `web/`). She turns the measurements into **decisions people use in the field**: status per vehicle with reasons, who is cut off, what to clear first, quality checks before mapping, and the offline delivery (server, phone field page, QR, hotspot).

## Folders
| Folder | Owner | Notes |
|---|---|---|
| `roads/` | Lead (back from her, 02:20) | DSM + OSM roads → `segments.geojson` and `places.geojson` for South Fork |
| `advisor/` | Her | Assessment engine, graph, routing, priorities, field reports, `/field` page |
| `quality/` (new) | Her | Image, metadata, coverage and overlap checks; builds on `pipeline/frame_quality.py` |
| `ml/` | Her | Image-quality model; optional road-status model |
| `api/` | **Her** (moved from lead) | The FastAPI app shell: offline serving, `/health`, tiles, mounts routers. The lead supplies `measure.router` and `accuracy.router` (`/spec`) |
| `web/` (all, incl. panels) | Lead (panels back from her, 02:20) | Map, 3D view, data panels, design system and styling. Panels read her `/advisor/*` JSON |
| `scripts/qr.py`, hotspot runbook | Her | |
| `neo4j/`, `config/vehicles.yaml`, `config/priority.yaml` | Her | Every number cited or `PLACEHOLDER` |
| `pipeline/ accuracy/ measure/ export/ config/quality.yaml` | Lead | She may import, not edit |
| `contracts/` | Shared | Changes only via the lead + `PLAN.md` decisions log |

**Hard rules:** no invented numbers (missing = `PLACEHOLDER`, mocks carry `"mock": true`); hand-written weights and rules are never called "AI"; no internet at runtime (downloads only in `scripts/prefetch_*.py`, run while online); "unknown" never becomes "open"; priorities are decision support, never "dispatch"; no CDN links in `web/` (bundle everything); ask before pushing; never force-push; if something is impossible or more than 2 hours late, stop and tell the lead.

**Vehicles (N1, decided by Claude per the lead's "decide this"; easy to change):** `fire_truck`, `ambulance`, `jeep`, `foot`. **Status words (N2):** data uses `open / partial / blocked / unknown`; the UI may show "accessible / restricted / inaccessible / unknown".

---

## Plan, in this order (one feature at a time)

### Must: ready for integration at 16:00 IST
| # | Deliverable | Done when | Target |
|---|---|---|---|
| T1 | **Neo4j** via `neo4j/docker-compose.yml`, tag pinned, GDS plugin downloaded once online | Restart with Wi-Fi off still prints `gds.version()` | 05:00 |
| T2 | **Vehicle profiles** `config/vehicles.yaml`: width, height, clearance per vehicle, cited or `PLACEHOLDER` | Every number has a source line | 06:00 |
| T3 | **Assessment engine** `advisor/assess.py`: segment measurements + profiles → status per vehicle + `reasons_by_mode` (rule + numbers) + `needs_verification` | Unit tests cover each rule, including missing data → `unknown` | 08:00 |
| T4 | **Graph + routing per vehicle** → `access_report.json`: reachability, isolated places, alternative routes; NetworkX fallback gives identical JSON | Neo4j and NetworkX outputs match on mock data | 10:00 |
| T5 | **Reopen plan** (= "impact of road restoration"): rank blocked segments by people/places reconnected per vehicle | Ranks with reasons in `access_report.json` | 11:00 |
| T6 | **Wayanad scenario**: OSM roads prefetched, road states from cited reports, labelled "scenario reconstructed from reports, not drone-measured" | Runs end to end through T3–T5; sources listed | 12:00 |
| T7 | **API app shell** `api/`: FastAPI on `0.0.0.0:8000`, serves built `web/`, tiles and all routers; `GET /health` says truthfully whether internet is reachable; advisor routes `GET /advisor/state`, `GET /advisor/priorities`, `POST /advisor/reports` | Starts with Wi-Fi off; lead's routers mount with one line each | 13:00 |
| T8 | **Field page** `/field` + field reports in SQLite (dead end, cleared, new debris), shown as `source: field_report`; **freshness line**; `scripts/qr.py`; hotspot runbook | A phone on the laptop hotspot opens it with Wi-Fi off; a report changes `/advisor/state` | 14:30 |
| ~~T9~~ | Road measurements → **moved to the lead** (02:20). She receives `segments.geojson` + `places.geojson` for South Fork ~15:00 | | |
| ~~T10~~ | Data panels → **moved to the lead** (02:20). The lead's panels read her `/advisor/state`, `/advisor/priorities`, `access_report.json` | | |

### Should
| # | Deliverable | Done when | Target |
|---|---|---|---|
| T11 | **Priority engine** → `priorities.json`: weighted score with factor breakdown, reasons, recommended action; weights in `config/priority.yaml` marked `PLACEHOLDER`; missing population = unknown, never 0. Demo: change one road, priorities recompute | Test: unblocking a segment changes the ranking | 17:00 |
| T12 | **Image and coverage quality** `quality/`: GPS/metadata validation, exposure histogram, coverage (footprints vs area), overlap via ORB matching → `image_quality.json` with its `coverage` block. Builds on `pipeline/frame_quality.py` | Runs offline on the Neo 2 frames and the USGS subset | 17:00 |
| T13 | **ML image-quality model**: only if it beats the standard check on frames she labels; otherwise report that, with numbers | Name, version, licence, training data and comparison written down | 18:00 |

### Could
T14 spatial confidence layer, labelled "estimated quality indicator" (never "accuracy") · T15 road-status ML scores via a pre-trained CRASAR model → `ml_scores.json`, fused in T3 (a model never flips a geometric "blocked" to "open") · T16 WorldPop population (CC BY 4.0, prefetched, cited) · T17 situation-report translation (Sarvam Translate, GPL-3.0).

### Later (after 31 Oct; kept so nothing is lost)
Automatic flight planning and adaptive re-flight (the Neo 2 cannot fly automated grids) · terrain-aware altitude · Bayesian/AHP priorities · training road/debris segmentation · before/after survey consistency (needs two of our own flights) · PWA service worker.

### If she falls behind, cut in this order
T17 → T16 → T14 → T15 → T13 → T12 → T11 → T6 (use South Fork only). T1–T5, T7 and T8 are the demo; they don't get cut.

---

## Decisions (31 Oct 02:00)
| # | Topic | Decision |
|---|---|---|
| R1 | Accuracy validator (checkpoints, RMSE, relative distances) | **Lead.** She does only T14 |
| R2 | Offline delivery: server, phone access, QR, hotspot, data sections | **Her** for server, field page, QR, hotspot (T7, T8). Data sections (panels) moved to the lead at 02:20: one `web/`, one owner |
| R3 | Road width, obstruction, debris per segment | **Lead** (moved back at 02:20: needs the lead's DSM, reuses `measure/` code, fits ODM waits) |
| R4 | Blur / exposure / GPS checks | **Her** (T12), extending `pipeline/frame_quality.py` |
| R5 | "Impact of road restoration" vs reopen plan | Merged (T5), hers |
| R6 | Status per vehicle + reasons | **Her** (T3), published via `/advisor/state` |
| O1 | Her docs assume F1–F5 flights, ArUco checkpoints, tape distances | Out of date (rain). Validation = USGS RTK + Neo 2 video |
| O2 | Training a segmentation model | Not by 21:30 → Later; T15 uses a pre-trained model only |

## Contract changes made for this plan (logged in PLAN.md)
`fire_truck / ambulance / jeep / foot` everywhere modes appear · `advisor_state` adds `reasons_by_mode`, `needs_verification` · `segments.geojson` `status_by_mode` now optional · new `priorities.json` · `image_quality.json` optional `coverage` block.

## What she gets from us, and when
- Contract mocks: **now** (`contracts/examples/`)
- `pipeline/frame_quality.py`, `pipeline/video_check.py`: **now**
- South Fork `segments.geojson` + `places.geojson` (incl. landing zones): ~15:00
- `measure.router` and `accuracy.router` to mount: ~15:00
- Built `web/` to serve: ~18:00
