# Prompt for the teammate's agent: Vortex route advisor, field delivery and quality checks

Paste everything below into your agent (Claude Code or similar), run from the root of the `vortex` repo the lead sent you.

---

## 1. Context

You are working on **Vortex**, a hackFront India 2026 prototype for PS T8.2 "The First Map After The Landslide": consumer drone footage → georeferenced map → road status and decisions for responders, **entirely offline on a laptop**. Prototype submission closes **31 Oct 2026, 11:59 pm IST; code freeze 9:30 pm IST.**

The team is split in two:
- **The lead (with their agent)** builds the map and everything on screen: ODM processing, positional accuracy, road segment measurements from the height model (`segments.geojson`, `places.geojson`), span / debris volume / landing zones / working space, exports, and all of `web/` (map, 3D view, data panels, styling).
- **You** turn those measurements into **decisions people use in the field**: road status per vehicle with reasons, who is cut off, what to clear first, quality checks before mapping, and the offline delivery (server app, phone field page, QR code, hotspot).

**Read these first, in this order:**
1. `TEAMMATE.md` (your scope, the decisions behind it, and the cut order)
2. `PLAN.md` (owners, timeline, decisions log; "Owners" and "Decisions log" sections)
3. `contracts/*.schema.json` and `contracts/examples/*` (the data formats you read and write; your outputs must validate)
4. `tests/test_contracts.py` (how contracts are tested; copy the pattern)
5. `pipeline/frame_quality.py` and `pipeline/video_check.py` (the existing brightness + sharpness check you extend in T12)
6. `CLAUDE.md` sections 1 (problem statement), 0 (hard rules) and 10 (access graph interface)

Setup: Windows, Docker Desktop, Python via `uv` (`uv sync`, `uv run pytest`). Vehicles are `fire_truck`, `ambulance`, `jeep`, `foot`. Statuses in data are `open / partial / blocked / unknown`.

## 2. Files you may and may not change

**You may create and change:** `advisor/`, `quality/`, `ml/`, `api/`, `neo4j/`, `scripts/qr.py`, `scripts/prefetch_wayanad.py` (and other `scripts/prefetch_*.py` you need), `config/vehicles.yaml`, `config/priority.yaml`, `docs/runbook_advisor.md`, and your own tests `tests/test_advisor_*.py`, `tests/test_quality_*.py`, `tests/test_api_*.py`. You may **add dependencies** to `pyproject.toml` (and let `uv` update `uv.lock`); list them in your report.

**You may read and import, never edit:** `pipeline/`, `accuracy/`, `measure/`, `roads/`, `export/`, `web/`, `config/quality.yaml`, `contracts/`, `PLAN.md`, `TEAMMATE.md`, `CLAUDE.md`.

**Contracts are frozen.** If a contract is missing something you need, stop and send the lead the exact field you want and why. Do not edit `contracts/`.

## 3. Hard rules

1. **Never invent a number.** Every value comes from a file, a run, or a cited source, or is labelled `PLACEHOLDER` (config) or `null` (data). Mock data carries `"mock": true` and obviously fake values.
2. **Missing data is "unknown", never "open", never 0.** Missing population is unknown, not zero people.
3. **Name things honestly.** Hand-written rules and weights are never called "AI" or "model". The priority output is "decision support", never "dispatch". Only a trained model you can name, version and evaluate may be called a model.
4. **Offline at runtime.** The API, advisor, field page and quality checks make **no internet calls** (the only exception: `GET /health` testing whether internet is reachable). All downloads happen in `scripts/prefetch_*.py`, run while online. No CDN links in any page you serve.
5. **A model never silently flips a geometric "blocked" to "open".** Disagreement → `needs_verification: true`.
6. **Licences:** write every external dataset or model you use (source, licence, date, purpose) into a section of your report; the lead adds it to `data/LICENSES.md`. OSM is ODbL; WorldPop is CC BY 4.0; Sarvam Translate is GPL-3.0.
7. **No secrets in git.** The Neo4j password goes in `.env` (gitignored), never in code or compose files.
8. **Git:** work on a branch named `teammate`. Small commits with clear messages. **Never push to `main`, never force-push, never rewrite history.** Ask the lead before pushing anywhere.
9. **If something is impossible, or will take more than 2 hours beyond its target, stop and tell the lead with options.** Don't improvise around it.

## 4. Steps, in this order (one at a time; each ends with tests passing)

### Must (ready for integration at 16:00 IST)
1. **T1 Neo4j.** `neo4j/docker-compose.yml` per `CLAUDE.md` section 10, with the GDS plugin. Start it once while online so the plugin downloads into the mounted `plugins` folder; pin the image tag you pulled (write it in your report). **Done when** a restart with Wi-Fi off still answers `RETURN gds.version();`.
2. **T2 Vehicle profiles** in `config/vehicles.yaml`: width, height, required clearance per side, and any limits you use (e.g. max obstruction height for `foot`), for each of the four vehicles. Each number has a `source:` line (spec sheet URL + date retrieved) or is marked `PLACEHOLDER`. Prefer Indian vehicles in real use (e.g. a common ambulance van, a state fire tender, a common 4x4 jeep).
3. **T3 Assessment engine** `advisor/assess.py`: input = segment properties from `segments.geojson` (`min_clear_width_m`, `max_obstruction_m`, `obstructed_length_m`, `coverage_fraction`, tolerances, optional `ml.p_blocked`) + `config/vehicles.yaml`; output per segment and vehicle = status + `reasons_by_mode` (the rule that fired, with the numbers it used) + `needs_verification`. Use `unknown` when coverage is low or a value sits within its tolerance of a threshold. **Done when** unit tests on hand-made segments cover every rule, including missing data → `unknown`.
4. **T4 Graph + routing per vehicle.** Load segments + places into Neo4j (`python -m advisor.load --project <p>`); compute reachability per vehicle from a configurable "base" place, isolated places, alternative routes → `access_report.json` (`python -m advisor.report --project <p> --out ...`). A NetworkX fallback must produce **identical JSON**. **Done when** a test shows Neo4j and NetworkX outputs match on mock data, and the output validates against `contracts/access_report.schema.json`.
5. **T5 Reopen plan** inside `access_report.json`: rank blocked segments by people and places reconnected per vehicle if cleared, with `reasons`. (This is also your docs' "impact of road restoration": one feature, not two.)
6. **T6 Wayanad scenario.** `scripts/prefetch_wayanad.py` saves OSM roads and places for the Chooralmala/Mundakkai area (small bounding box) as GeoPackage/GeoJSON. Road states come from cited reports (URL + date per state). Everything carries the label "scenario reconstructed from reports, not drone-measured". **Done when** it runs end to end through T3–T5 offline, with sources listed.
7. **T7 API app shell** `api/main.py`: FastAPI on `0.0.0.0:8000`. Mount your `advisor.router` at `/advisor` with `GET /advisor/state` (validates against `contracts/advisor_state.schema.json`), `GET /advisor/priorities`, `GET /advisor/access`, `POST /advisor/reports`. Mount the lead's routers **if importable** (`measure.router`, `accuracy.router`); if not yet, start anyway and log that they're missing. Serve `web/dist/` at `/` if it exists, and tiles from `data/projects/<p>/tiles/`. `GET /health` reports whether internet is reachable (1-second socket test), truthfully. **Done when** it starts with Wi-Fi off and a test hits every route.
8. **T8 Field page** at `/field`: mobile-first, plain HTML/CSS/JS, everything bundled locally. The default is "pick where you are" from a list of nearby places/segments (no map dependency; a map can be added later from the lead's `web/`). Report `dead_end`, `cleared`, `new_debris` or `other` for a segment and vehicle(s), with an optional note; stored in SQLite under `data/advisor/` (gitignored). Reports show in `/advisor/state` as `source: "field_report"`. Show a **freshness line**: survey time, analysis time, number of field reports. Also `scripts/qr.py` (prints a QR code for `http://<laptop-ip>:8000/field`) and `docs/runbook_advisor.md` (Windows Mobile Hotspot steps, firewall rule for port 8000 on private networks only, start order). **Done when** a phone joined to the laptop's hotspot opens `/field` with Wi-Fi off, submits a report, and `/advisor/state` changes. The lead reviews the look before 18:00.

### Should (by 18:00)
9. **T11 Priority engine** → `priorities.json` (validates against `contracts/priorities.schema.json`, `decision_support: true`): weighted score per place with factor breakdown, `unknown_factors`, reasons and a recommended action. Weights live in `config/priority.yaml`, marked `PLACEHOLDER`. **Done when** a test shows that changing one segment from blocked to open changes the ranking (this is a demo moment).
10. **T12 Image and coverage quality** `quality/`: per-image GPS and metadata validation (exiftool), exposure histogram, coverage (image footprints vs survey area), overlap between neighbours via ORB feature matching → `image_quality.json` with its `coverage` block. **Import** `pipeline/frame_quality.py` for blur and brightness; don't re-implement them. Thresholds go in your own config, marked `PLACEHOLDER` until calibrated. **Done when** it runs offline on the lead's Neo 2 frames and USGS subset (ask the lead for paths).
11. **T13 ML image-quality model** (optional within Should): only if, on frames you label yourself, it beats the standard check from step 10. Report either way, with the numbers. Write down the model name, version, licence and training data.

### Could (only if everything above is done)
T14 spatial confidence layer over the orthophoto, labelled "estimated quality indicator" (never "accuracy") · T15 pre-trained CRASAR road-damage scores → `ml_scores.json`, fused in T3 under rule 5 · T16 WorldPop population, prefetched and cited · T17 situation-report translation (Sarvam Translate).

**If you fall behind, cut in this order:** T17 → T16 → T14 → T15 → T13 → T12 → T11 → T6 (use South Fork only). T1–T5, T7 and T8 are the demo and are not cut.

## 5. What you get from the lead, and when
- Contract mocks: now, in `contracts/examples/`. **Build everything against these first.**
- Real South Fork `segments.geojson` + `places.geojson` (incl. landing zones): ~15:00
- `measure.router` and `accuracy.router` to mount: ~15:00
- Built `web/dist/` to serve: ~18:00

## 6. Definition of done
- Every Must step's "done when" is met, and `uv run pytest` passes with your tests included.
- `GET /advisor/state`, `access_report.json` and `priorities.json` validate against their contracts on both mock data and the Wayanad scenario.
- The whole advisor runs with Wi-Fi off: Neo4j (or the NetworkX fallback), the API, and the field page on a phone over the hotspot.
- No number without a source or a `PLACEHOLDER` label; no "AI" label on rules or weights.
- `docs/runbook_advisor.md` lets the lead start everything on **their** laptop from a clean clone (the demo runs there): commands in order, what each prints, and the one-time online step for the Neo4j plugin.

## 7. Time limits and check-ins
- Send the lead a 3-line status at **06:00, 10:00, 13:00 and 16:00 IST**: done, in progress, blocked.
- Must by **16:00**, Should by **18:00**. **Stop feature work at 21:00** for the 21:30 code freeze.
- If something is impossible, stop and tell the lead instead of improvising.

## 8. What to send back (at each check-in, and at the end)
1. Branch name and latest commit hash (or a `git bundle` file if not pushed).
2. Output of `uv run pytest`.
3. Which steps are done, which aren't, and why.
4. Every `PLACEHOLDER` you left, and every source and licence you used.
5. New dependencies you added.
6. Anything you need changed in a contract (field, type, reason).
