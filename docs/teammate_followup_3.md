# Follow-up 3 for the teammate's agent: real-data fixes, then finish

**Status: READY (31 Oct 18:30 IST).** Your branch `teammate` @ `001c70f` is **merged into `main`** (no conflicts; 99 tests pass, 2 skipped only because Neo4j and Wayanad aren't set up on the lead's laptop). Thank you: exports, situation report, sources and tests all landed.

The lead's side then ran your advisor and exports on the **real** South Fork block. They work, and found the problems below. This is everything left for you before the freeze. Paste everything below into your agent, run from the root of the `vortex` repo.

---

## 1. Context
- Product name is **Project Typhon** (team Vortex). Code freeze **21:30 IST**. **Stop feature work 20:30 IST, push by 20:15 IST.**
- Real files for testing are in `samples/southfork_f01_4/` (updated today: accuracy is now **±6.09 m at 3 checkpoints**, after converting the USGS checkpoints from NAD83(2011) to WGS84; relative heights ±1.09 m).
- What the real data looks like: `segments.geojson` holds **498** OSM road pieces; only **16 have `measured: true`** (inside the photographed area); the other 482 are outside the map. All 498 come out `unknown`, which is correct. No landing zones. Two places: `osm_place_0` (South Fork Campground, the staging base) and `osm_place_1`.

**Before you start:**
```
git fetch origin
git checkout teammate
git merge origin/main
uv sync
uv run pytest -q
```

## 2. Files you may change
`advisor/ quality/ ml/ api/ neo4j/ export/`, `advisor/static/` (restyle), your scripts and configs, your tests, `docs/runbook_advisor.md`, `docs/sources_teammate.md`, and a new `docs/teammate_report.md`. **Read-only:** everything else, including `samples/`, `contracts/`, `web/`, `PLAN.md`, `TEAMMATE.md`.

## 3. Hard rules (unchanged)
No invented numbers; **unknown ≠ open and unknown ≠ blocked**; no "AI" on rules; offline at runtime; work on `teammate`; never push to `main`; never force-push; no AI co-author lines in commits (log AI use in `docs/AI_DISCLOSURE.md`); if something will take more than 30 min beyond its slot, stop and tell the lead.

## 4. Steps, in this order

### F1. Honest reasons when roads are unknown (must, 40 min)
On the real data `/advisor/priorities?project=southfork_f01_4` currently says:
- `osm_place_1`: **"completely cut off (unreachable even on foot)"**, level `critical`. Nothing is blocked; its roads are just **unverified**.
- `osm_place_0`: **"reachable by all vehicle classes including fire_truck and ambulance"** and **"Single passable corridor"**, while its connecting road is `unknown`. It's the staging base, so it is trivially reachable, but the wording reads as if unknown roads were passable.

The lead's dashboard shows these reasons word for word, so this is the most visible thing to fix.
Fix in `advisor/` (access + priorities):
1. Separate **cut off** (every route has a `blocked` segment) from **access unverified** (no route is known-open, but some are `unknown`). Use those exact words in reasons, e.g. "access unverified: connecting roads seg_0005 not yet assessed".
2. The staging base gets "staging base" in its reasons, never "reachable by all vehicle classes".
3. Never call an `unknown` segment "passable" or count it as a "passable route".
4. Unverified places can still rank high (they need checking), but the reason must say **verify**, not "cut off". If `access` has an isolated-places list, add the unverified ones separately (e.g. `unverified_places_by_mode`) **without changing existing contract fields**; if you think the contract needs a change, ask the lead first.

**Done when:** a test on `samples/southfork_f01_4/` asserts no reason contains "cut off", "passable" or "reachable by all" for places whose roads are only `unknown`, and a synthetic test with a truly `blocked` route still says "cut off".

### F2. PDF map on real data (must, 40 min)
Run `uv run python -m export.all --project southfork_f01_4 --out <dir> --project-dir samples/southfork_f01_4 --orthophoto samples/southfork_f01_4/orthophoto_small.tif --accuracy samples/southfork_f01_4/accuracy.json` (adjust to how your inputs resolve). On the lead's laptop the A3 PDF showed:
1. **Extent:** zoomed out to all 498 pieces (~10 km); the photographed area is a speck. → Fit the map to the **orthophoto bounds** (fall back to `measured: true` segments, then all). Segments outside can stay, clipped.
2. **Title** says "VORTEX POST-LANDSLIDE…". → "Project Typhon: road access map: <project>".
3. **"Survey / analysis time"** prints `run.json`'s processing end time (today), but the USGS flight was 30 Apr 2024. → Label it **"Processed"**. Show a capture date only if an input provides one (add an optional `--captured` CLI flag); otherwise "capture date: not recorded".
4. **Data basis** says "Drone photogrammetry assessment". → Add an optional `--basis` flag; for South Fork the lead will pass "USGS public data (30 Apr 2024), not our footage". Default: "not stated".
5. **Layer summary** says "unknown=498". → Split into "unknown inside mapped area: 16" and "outside mapped area: 482" using `measured`.
Same extent and labels in the KMZ's document name/description where it applies.

**Done when:** tests cover 1–5 on the sample files, and you've looked at the rendered PDF yourself.

### F3. Restyle `/field` (must, 45 min; was follow-up 2 step 4)
Use the brand tokens in `web/src/styles/tokens.css` (copy the values; your page is served separately): forest `#2F3E2E` primary buttons and bottom bar, sand `#F8F6EF` background, stone `#E6E1D6` cards, Space Grotesk headings, Inter body (system fallbacks fine offline). Status chips match the dashboard: open green `#2E7D4F` solid, partial amber `#C98A12` dashed, blocked red `#B3261E` with ✕, unknown grey `#8C918A` dotted. Title "Project Typhon: field report". No CDN, no web fonts from the internet.
**Done when:** a phone-width screenshot (390 px) of the form and of the confirmation; the lead approves the look.

### F4. Screenshots of the real exports (should, 15 min)
Open the GeoPackage from F2 in QGIS and the KMZ in Google Earth (Desktop or Web). One screenshot each.

### F5. T14 spatial confidence layer (only if F1–F4 are done before 19:45)
On `orthophoto_small.tif`, labelled "estimated quality indicator", never "accuracy".

### F6. Report (must, 15 min) → new file `docs/teammate_report.md`
1. Branch + commit hash; `uv run pytest -q -rs` output (explain every skip)
2. **V1** Neo4j offline: worked? image tag + GDS version
3. **V2** Wayanad end to end offline: roads, places, blocked counts
4. **V3** phone test of `/field`: worked? firewall rule used; screenshots
5. **M1** BRISQUE vs standard check: precision/recall for both, which wins (if not run, say so)
6. **C1** WorldPop: method (radius and why); **C2** situation report: languages; **C3** road-damage model: ran offline or not
7. F1–F5 results with screenshots
8. Every `PLACEHOLDER` still open; new dependencies; contract change requests

Push `teammate` **by 20:15 IST** and tell the lead. The lead merges, runs the end-to-end offline check, and builds the deck.
