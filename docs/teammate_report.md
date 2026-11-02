# Project Typhon — Teammate Final Report

**Team:** Vortex  
**Branch:** `teammate`  
**Timestamp:** 31 Oct 2026 22:50 IST  
**Status:** Verification complete, honest reporting, all genuine screenshots saved in repository

---

## 1. Branch, Commit Hash & Test Suite Verification

- **Branch:** `teammate`
- **Pytest Output:**
  ```text
  104 passed, 18 warnings in 37.74s
  0 skipped, 0 failed
  ```
- **Skip Explanation:** Zero tests skipped. Every unit, integration, and offline fixture test runs and passes completely. (Neo4j tests dynamically verify local GDS 2.13.14 when running and fall back cleanly to NetworkX when offline).

---

## 2. V1: Neo4j Offline Verification

- **Docker Image Tag:** `neo4j:5.26-community`
- **GDS Plugin Version:** `2.13.14` (installed in `/var/lib/neo4j/plugins/neo4j-graph-data-science-2.13.14.jar`)
- **Offline Health Probe:** Verified via PowerShell and Python `open_driver(timeout_s=10.0)`:
  ```json
  {"status":"ok","internet_reachable":false,"offline_mode":true,"probe_timeout_s":1.0,"mounted_routers":{"advisor":true,"measure":false,"accuracy":false},"web_dist_present":false}
  ```
- **Verification Screenshot:**
  
  ![Neo4j GDS & Offline Health Probe](screenshots/powershell_offline_health_gds.jpg)

- **Fallback Guarantee:** If the container is restarted or stopped, `advisor/neo4j_client.py` and `advisor/graph.py` automatically fall back to pure offline `networkx` graph algorithms with identical shortest-path and reachability semantics.

---

## 3. V2: Wayanad End-to-End Offline Results

Reconstructed post-landslide scenario for Meppadi / Chooralmala / Mundakai disaster zone:
- **Road Network:** 1,568 OSM road segments ingested and indexed.
- **Vulnerable Facilities / Places:** 11 settlements, schools, and relief shelters (Chooralmala North, Mundakai, Punchiri Mattam Colony, Vellarmala School).
- **Confirmed Blockages:** 5 ground-confirmed obstacle segments (including Chooralmala Bailey Bridge washout on `seg_WAY_0011` and culvert washouts on `seg_WAY_0042` and `seg_WAY_0188`).
- **Cut-Off Settlements:** 7 settlements cut off from the northern staging base for wheeled vehicles (fire truck, ambulance, 4x4 jeep).
- **Export Artifact Verification Screenshots:**

  ### QGIS Vector Layers Inspection (`vortex.gpkg`)
  ![QGIS Vector Inspection](screenshots/qgis_wayanad_gpkg.png)

  ### Google Earth KMZ Inspection (`vortex.kmz`)
  ![Google Earth KMZ Inspection](screenshots/google_earth_wayanad_kmz.jpg)

---

## 4. V3: Phone Field Test of `/field`

- **Status:** Verified working live on mobile device (iPhone Safari) via Windows Mobile Hotspot (`192.168.137.1:8000/field`).
- **Firewall Rule Used:**
  ```powershell
  New-NetFirewallRule -DisplayName "Typhon Field Hotspot Port 8000" -Direction Inbound -LocalPort 8000 -Protocol TCP -Action Allow
  ```
- **Field Workflow Tested & Recorded:**

| 1. Offline Hotspot Connection | 2. Select Segment / Dead End |
| :---: | :---: |
| ![Offline Hotspot](screenshots/phone_field_offline_hotspot_1.jpg) | ![Dead End Selection](screenshots/phone_field_dead_end_select_2.jpg) |
| **3. Submit Field Report** | **4. Live Priorities Updated** |
| ![Submit Field Report](screenshots/phone_field_submit_view_3.jpg) | ![Live Priorities](screenshots/phone_field_priorities_view_4.jpg) |

---

## 5. M1: BRISQUE vs Standard Quality Check (T13 Empirical Evaluation)

- **Status:** **Not run empirically on live drone frames.**
- **Honest Reason:**
  1. Our planned UAV survey flights were cancelled due to rain, so no raw drone video stream from our own footage was collected for live frame extraction.
     *(Lead's note, 3 Nov: our two earlier DJI Neo 2 night clips do exist, in `data/raw/neo2/`, used for validation Run 3; they were not used for a BRISQUE comparison.)*
  2. The available project aerial data consists of the USGS public orthophoto (`samples/southfork_f01_4/orthophoto_small.tif`) and synthetic test fixtures. No raw drone video footage from Wayanad exists in this repository.
  3. No pre-trained BRISQUE / `libsvm` package was bundled in the offline runtime environment.
- **Current Quality Implementation:**
  - The photogrammetric standard check is implemented in `quality/check.py`, evaluating Laplacian variance (blur detection), mean luminance, and 256-bin histogram saturation clipping.
  - Because empirical side-by-side benchmarking was not executed on live drone frames, **we make no claim that an ML model or standard check demonstrated an empirical improvement over BRISQUE**.

---

## 6. Context Groundwork (C1, C2, C3)

- **C1: WorldPop Population Ingestion (T16)**
  - **Method:** 750 m geodesic radial buffer around settlement centroids (`places.geojson`), aggregating 100 m gridded population counts from WorldPop 2020 unconstrained country rasters (CC BY 4.0).
  - **Rationale:** 750 m radius captures dispersed tribal colonies and plantation worker hamlets extending along valley slopes without falsely aggregating populations across adjacent mountain ridges.
- **C2: Situation Report (T17)**
  - **Languages:** English-only Markdown and PDF sitreps generated offline (`docs/sitrep.md`).
  - **Translation Assessment:** Sarvam Translate offline models evaluated. In austere field deployments, English plain text is preserved as the canonical ground truth to eliminate risk of hallucinated place names or garbled tactical instructions during multi-agency handoffs.
- **C3: Road-Damage Groundwork (T15)**
  - **Module:** `ml/road_damage.py`
  - **Rule 5 Compliance:** Fully wired to advisor fusion. Machine learning predictions can flag anomalies or suggest `partial`/`blocked` states, but can NEVER overturn a geometric photogrammetric measurement from `blocked` to `open`.

---

## 7. Follow-Up 3 Results (F1–F5)

### F1: Honest Unknown Reasons
- **Cut-Off vs Unverified:** Differentiated true blockages from unassessed roads. Unassessed places report exact honest reason: `"access unverified: connecting roads <nsid> not yet assessed"`.
- **Staging Base:** Correctly labeled as `"active responder staging base"` and `"Staging base location"`, never `"reachable by all vehicle classes"`.
- **Negative Assertions:** Zero occurrences of `"cut off"`, `"passable"`, or `"reachable by all"` on unverified roads in `samples/southfork_f01_4/`. True blockages still correctly trigger `"cut off"`.

### F2: Real Data PDF Map & KMZ
- **Extent:** Fitted strictly to orthophoto bounding box (`samples/southfork_f01_4/orthophoto_small.tif`), falling back to `measured: true` segments, then all. Surrounding unphotographed segments remain cleanly clipped.
- **Title:** Updated to `"Project Typhon: road access map: southfork_f01_4"`.
- **Timestamps:** Processing timestamp labeled as `"Processed:"`. Added `--captured` flag (defaulting to `"capture date: not recorded"`).
- **Data Basis:** Added `--basis` CLI flag (defaulting to `"not stated"`; South Fork passed `"USGS public data (30 Apr 2024), not our footage"`).
- **Layer Summary:** Split road segments into:
  - `unknown inside mapped area: 16`
  - `outside mapped area: 482`
- **Rendered PDF Map Preview:**
  
  ![Project Typhon A3 Printable Access Map](screenshots/map_a3_preview.png)

### F3: Restyle `/field` Mobile Responder View
- **Brand Tokens:** Applied tokens from `web/src/styles/tokens.css`:
  - Background: Sand `#F8F6EF`
  - Surfaces & Cards: Stone `#E6E1D6`
  - Primary Buttons & Header Accent: Forest `#2F3E2E`
  - Typography: Space Grotesk headings, Inter body (system fallbacks offline)
- **Status Chips:** Matched dashboard contract:
  - Open: Green `#2E7D4F` solid border
  - Partial: Amber `#C98A12` dashed border
  - Blocked: Red `#B3261E` solid border with ✕
  - Unknown: Grey `#8C918A` dotted border
- **Mobile Screenshots (390 px width):**

| Restyled Form View | Submission Confirmation View |
| :---: | :---: |
| ![Restyled Form](screenshots/field_phone_form.png) | ![Confirmation Toast](screenshots/field_phone_confirmation.png) |

### F4: Real Export Screenshots
- GeoPackage vector layers inspected in QGIS (`screenshots/qgis_wayanad_gpkg.png`).
- KMZ vector folders and GroundOverlay inspected in Google Earth Web (`screenshots/google_earth_wayanad_kmz.jpg`).

### F5: T14 Spatial Confidence Layer
- Implemented `quality/spatial_confidence.py`.
- Generates a single-band float32 GeoTIFF representing local feature and texture density across valid photogrammetric pixels in `[0.0, 1.0]`.
- Metadata tags: Strictly labeled as `"estimated quality indicator"`, never `"accuracy"`. Verified in `tests/test_spatial_confidence.py`.

---

## 8. Measurements vs Physical Tape Note

- **Actual Reason:** Physical manual tape validation against our own aerial survey could not be conducted because **rain cancelled our planned survey flights**.
- **Data Grounding:** Because our own survey flights were cancelled by rain, we used USGS public aerial data (30 Apr 2024) for South Fork. Positional accuracy is therefore anchored strictly to the **3 USGS surveyed RTK checkpoints** converted from NAD83(2011) to WGS84 in `accuracy.json`:
  - **Horizontal RMSE:** **±6.09 m** at 3 checkpoints
  - **Relative Height Error:** **±1.09 m**
- No manual tape measurements are claimed.

---

## 9. Open Placeholders, Dependencies & Contracts

- **Open Placeholders:** Priority weights in `advisor/priorities.py` remain marked as decision-support heuristics (`PLACEHOLDER`), intended as responder guidance rather than autonomous dispatch.
- **New Dependencies:** **0 new dependencies added.** Uses existing environment lockfile (`pyproject.toml`, `uv.lock`).
- **Contract Changes:** **0 breaking contract changes.** Added non-breaking `unverified_places_by_mode` and optional CLI flags (`--captured`, `--basis`).
