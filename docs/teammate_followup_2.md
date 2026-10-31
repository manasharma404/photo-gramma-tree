# Follow-up 2 for the teammate's agent: real data, integration, finish

**Status: DRAFT, sent when the lead's real South Fork files are in `samples/`.**

Paste everything below into your agent, run from the root of the `vortex` repo.

---

## 1. Context (as of 31 Oct afternoon, IST)

- The product is now **Project Typhon** (team name stays Vortex). The web app (`web/`) has a landing page at `/` and the dashboard at `/app/`. Your `api/main.py` serves both, plus your `/field` page. Internal names like `VORTEX_*` are unchanged.
- Your round 1 is merged. Follow-up 1 (verification, sources, exports) is yours to finish first if not done. **Push it to `teammate` before starting this.**
- **Code freeze is 21:30 IST.** Stop feature work at 20:30 IST.
- Our data folder is not in git. The lead has put small **real** files in `samples/southfork_f01_4/`:
  - `segments.geojson`: real road segments with measurements, from the 5-line USGS block (OSM ODbL, USGS public domain)
  - `places.geojson`: places plus landing-zone candidates
  - `accuracy.json`: real accuracy (horizontal ±6.4 m RMSE at 3 checkpoints; vertical as measured)
  - `orthophoto_small.tif`: a downsampled orthophoto (for exports and T14)
  - `README.md`: what each file is and its licence line

**Before you start:**
```
git fetch origin
git checkout teammate
git merge origin/main
uv sync
uv run pytest -q
```

## 2. Files you may change
Same as follow-up 1 (`advisor/ quality/ ml/ api/ neo4j/ export/`, your scripts and configs, your tests), **plus** `advisor/static/` for restyling (step 4). Read-only: everything else, including `samples/` and `contracts/`.

## 3. Hard rules (unchanged)
No invented numbers; unknown ≠ open; no "AI" on rules; offline at runtime; work on `teammate`; never push to `main`; never force-push; no AI co-author lines in commits; stop and ask if something will take more than an hour beyond its slot.

## 4. Steps, in this order

1. **Run on real data (30 min).** Point your assessment, graph, reopen plan and priorities at `samples/southfork_f01_4/` (e.g. copy into `data/projects/southfork_f01_4/roads/` on your laptop). Report: segments per status per vehicle, places cut off per vehicle, the top 3 priorities, and anything in our files that broke your assumptions (e.g. footpaths only, low coverage under canopy).
   **Done when:** `/advisor/state?project=southfork_f01_4`, `/advisor/access` and `/advisor/priorities` return valid contract JSON on the real files, with a test.
2. **Exports on real data (30 min).** Run `python -m export.all --project southfork_f01_4` against the sample files and the small orthophoto. Open the GeoPackage in QGIS and the KMZ in Google Earth; send a screenshot of each. The PDF's accuracy line must read from `accuracy.json`.
3. **T14 spatial confidence layer (optional, 45 min)** on `orthophoto_small.tif`, labelled "estimated quality indicator", never "accuracy".
4. **Restyle `/field` (45 min)** to the Project Typhon brand. Use the colour and type tokens in `web/src/styles/tokens.css` (copy the values; your page is served separately). Forest `#2F3E2E` for primary buttons and the bottom bar; sand `#F8F6EF` background; stone `#E6E1D6` cards; Space Grotesk headings, Inter body (system fallbacks are fine offline). Status chips use the same colours and patterns as the dashboard: open green solid, partial amber dashed, blocked red with ✕, unknown grey dotted. The lead approves the look.
5. **Push** `teammate` by **20:00 IST** and send the report below. The lead's side merges and runs the end-to-end offline check on the lead's laptop.

## 5. What to send back
Branch + commit; `uv run pytest` output; step 1 numbers; QGIS and Google Earth screenshots; a phone screenshot of the restyled `/field`; open PLACEHOLDERs; anything you need changed in a contract.
