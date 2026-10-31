# Follow-up 1 for the teammate's agent: finish everything that doesn't need the lead

Paste everything below into your agent, run from the root of the `vortex` repo.

---

## 1. Context

Your first round (T1–T8, T11–T13) was reviewed and **merged into `main`** on 31 Oct ~05:45 IST: everything stayed inside your folders, the honesty rules were followed, and 68 tests pass on the combined code. Thank you.

The review also found that several "done when" checks were never actually run: your agent worked in a sandbox, so Neo4j never started, the Wayanad data was never downloaded, and the field page was never opened on a phone. Some sources cite website home pages rather than a specific document. **This round closes all of that, and adds the exports** (moved to you from the lead).

**Rule for this round:** finish every item below that doesn't need the lead's outputs. Items that need the lead (real South Fork roads and places, the lead's routers, the built web app, real orthophotos) are listed in section 6, **not to be started**: the lead will send a second follow-up when they're ready.

**Before you start:**
```
git fetch origin
git checkout teammate
git merge origin/main
uv sync
uv run pytest -q
```
Expect `68 passed, 2 skipped` (the two skips are what step V1 and V2 fix).

**Read first:** `docs/teammate_prompt.md` (your original prompt; all its hard rules still apply), `TEAMMATE.md`, `contracts/*`, `docs/validation.md` (what the lead's map accuracy looks like so far, and why).

## 2. Files you may and may not change

Same as before (`advisor/ quality/ ml/ api/ neo4j/`, `scripts/qr.py`, `scripts/prefetch_*.py`, `config/vehicles.yaml`, `config/priority.yaml`, `docs/runbook_advisor.md`, your own tests), **plus, new this round:**
- `export/` (all of it) and `tests/test_export_*.py`
- `docs/sources_teammate.md` (new: your source list, see S1)

Still read-only for you: `pipeline/ accuracy/ measure/ roads/ web/ contracts/`, `PLAN.md`, `TEAMMATE.md`, `CLAUDE.md`, `config/quality.yaml`.

## 3. Hard rules (unchanged, repeated because they matter most)

1. Never invent a number or a source. Every value comes from a run, a file, or a **specific** cited document; otherwise `PLACEHOLDER` (config) or `null` (data).
2. Unknown is never "open" and never 0.
3. Rules and hand-set weights are never called "AI"; priorities are "decision support", never "dispatch".
4. No internet at runtime; downloads only in `scripts/prefetch_*.py`, run while online; no CDN links.
5. Git: work on `teammate`, small commits, **never push to `main`, never force-push**. No AI co-author lines in commit messages; AI use is logged in `docs/AI_DISCLOSURE.md` by the lead from your report.
6. If something is impossible or more than 2 hours over, stop and tell the lead with options.

## 4. Steps, in this order

### V: verify what was built (run for real, on your laptop, not in a sandbox)
**V1. Neo4j for real (T1).** Run `docker compose up -d` in `neo4j/` while online, so the GDS plugin downloads. Then turn Wi-Fi off, restart the container, and run `RETURN gds.version();`. Record the pinned image tag and the GDS version.
**Done when:** that works offline, and `tests/test_advisor_graph.py` runs its Neo4j test (no longer skipped) and passes, with Neo4j and NetworkX giving identical `access_report.json`.

**V2. Wayanad for real (T6).** Run `scripts/prefetch_wayanad.py` while online. Then, with Wi-Fi off, run it end to end through assessment → graph → `access_report.json` → `priorities.json`.
**Done when:** the skipped Wayanad test runs and passes, every output validates against its contract, and the report lists how many roads, places and blocked segments came out.

**V3. The API and field page on a real phone (T7, T8).** Start `api/main.py` on `0.0.0.0:8000` with Wi-Fi off. Turn on the laptop's Mobile Hotspot, join it from a phone, scan the QR from `scripts/qr.py`, open `/field`, and submit a `dead_end` report on a Wayanad segment.
**Done when:** `/advisor/state` changes for that segment with `source: "field_report"`. Take two phone screenshots (field page, confirmation) and note the exact firewall rule you used. Update `docs/runbook_advisor.md` with anything that differed from what it says.

**V4. `/health` honesty.** With Wi-Fi off, `/health` says internet is not reachable; with Wi-Fi on, reachable. Add a test that fakes both cases.

### S: sources
**S1. Make every source checkable.** For each value in `config/vehicles.yaml`, `config/priority.yaml` and each Wayanad road state:
- Replace home-page citations (e.g. `https://pib.gov.in/`, `https://mahafireservice.gov.in/`, `https://www.nrsc.gov.in/`) with the **specific** document or article URL, its date, and the clause, page or sentence that gives the number or state.
- If you can't find a specific source within ~10 minutes for a value, change it to `PLACEHOLDER` with the reason. **Don't keep a citation you couldn't open and read yourself.**
- Write `docs/sources_teammate.md`: one row per value or state, with URL, date, what it says (short quote of at most 15 words, or a paraphrase), and licence where relevant.

**Done when:** no home-page-only citation remains; a test fails if any `source:` field is just a domain.

### M: ML gate (T13)
**M1. Run the BRISQUE vs standard-check comparison on real frames.** You don't need the lead's data:
- Download one USGS South Fork image zip yourself in a browser (public domain; the smallest is `SEKI_SouthFork_AerialImages_F02-2.zip`, 470 MB, ScienceBase item `67353631d34e6fbce7b5d58f`). Keep it under `data/` (gitignored).
- Make some frames deliberately bad (blur, darkening, motion blur) **and label them as synthetic**.
- Label at least 50 frames `usable` yes/no yourself.

**Done when:** `ml/benchmark_iqa.py` prints precision/recall for both methods and you report which wins, with numbers. If BRISQUE doesn't win, say so; the pipeline keeps the standard check.

### C: the "Could" items you can do alone
**C1. Population (T16) for Wayanad.** Prefetch WorldPop (CC BY 4.0) for the Wayanad bounding box in a `scripts/prefetch_*.py`, and attach population per place with the method (e.g. sum of cells within X m: say what X is and why). Missing stays unknown.
**Done when:** `places` population and `population_source` are filled for Wayanad, and the reopen plan and priorities use them.

**C2. Situation report + translation (T17).** Generate a short situation report from `access_report.json` + `priorities.json` (Markdown and HTML, offline): cut-off places per vehicle, the top 3 reopen actions with reasons, the data time and the "scenario"/"measured" label. Translation: Sarvam Translate (GPL-3.0) **only if it runs offline on this laptop**; otherwise leave English-only and say why.
**Done when:** a Wayanad situation report is generated offline (English, plus Malayalam or Hindi if translation runs).

**C3. Road-damage ML scores (T15), groundwork only.** Wire a pre-trained CRASAR road-damage model (MIT licence on its model card) into `ml/` with a predict CLI that takes image crops per `segment_id` → `ml_scores.json`, and fuse it in `advisor/assess.py` under the rule "a model never flips a geometric blocked to open; disagreement → `needs_verification: true`". Test it on a few public images.
**Done when:** it runs offline on public images with tests for the fusion rule. **The real run on our orthophoto waits for the lead** (section 6). If the model can't run offline on this laptop in 1 hour, stop and report.

### E: exports (new, moved from the lead)
Build `export/` so a responder can open our results in the tools they already use. **Build and test everything against `contracts/examples/` plus a small synthetic GeoTIFF that your tests create** (a few hundred pixels, EPSG:32611). The real files arrive later (section 6).

**E1. GeoJSON (EPSG:4326)**: one file per layer: `roads_status` (segments + status per vehicle + reasons from `/advisor/state`), `cutoff_places`, `landing_zones`, `checkpoints` (from `accuracy.json`), `measurements` (from `measurement.json` files).
**E2. GeoPackage** `vortex.gpkg` with the same layers, for QGIS/ArcGIS.
**E3. KMZ** for Google Earth: vector layers as KML with styles that match the status (open / partial / blocked / unknown, by shape **and** colour); plus the orthophoto as a ground overlay (a downsampled PNG with its bounding box).
**E4. Cloud-Optimized GeoTIFF**: convert an orthophoto / DSM to COG (rasterio or `gdal_translate -of COG`), with a validity check.
**E5. Printable PDF map** (A3 landscape): orthophoto, road status overlay, coordinate grid, scale bar, north arrow, legend, survey date/time, and the accuracy line taken from `accuracy.json` ("±X m at N checkpoints"; if missing: "accuracy not measured yet", never a guess). Layout must be readable in black-and-white printing (status by line pattern, not only colour).
**E6. One command**: `python -m export.all --project <p> --out <dir>` produces all of the above and an `export_manifest.json` (file, format, CRS, layer counts, source files, generated_at).

**Done when:** tests open every output again (`geopandas.read_file` for GeoJSON and GPKG, unzip and parse the KMZ, a COG validity check, a PDF that exists and has one page). **You** open the GPKG in QGIS and the KMZ in Google Earth (Desktop or Web) on your laptop, and send one screenshot of each.

## 5. Check-ins and what to send back
- A 3-line status every 2 hours to the lead (done / in progress / blocked).
- At the end:
  1. branch + commit hash
  2. `uv run pytest` output (no skips left except ones you explain)
  3. phone screenshots (V3) and QGIS / Google Earth screenshots (E)
  4. ML gate numbers (M1)
  5. `docs/sources_teammate.md`
  6. every `PLACEHOLDER` you left
  7. new dependencies
  8. anything you need changed in a contract
- **Stop feature work by 20:30 IST** (code freeze 21:30).

## 6. Waiting on the lead: do NOT start these (they come in follow-up 2)
- Real South Fork `segments.geojson` and `places.geojson` (incl. landing zones) → run your assessment, graph, reopen plan and priorities on real data
- The lead's `measure.router` and `accuracy.router` → mount in `api/main.py` and test
- The built `web/dist/` → serve it from `api/` and test on a phone
- Real orthophoto and DSM → T12 coverage on real images, T14 spatial confidence layer, T15 real road-damage scores, and real exports
- Neo 2 video frames → T12/T13 on our own footage
- The end-to-end offline rehearsal on the lead's laptop
