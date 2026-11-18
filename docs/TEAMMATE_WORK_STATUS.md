# Team Vortex — Finale Groundwork Status & Handoff
**Date:** 18 November 2026  
**Product:** Project Typhon (team Vortex), hackFront PS T8.2 "The First Map After The Landslide"  
**Branch:** `teammate` (commit: `6e8c9cd`)  
**Test Suite:** `107 passed, 1 skipped, 18 warnings in 44.62s` (`uv run pytest -q`)  

---

## 1. Executive Summary

We have completed the ground preparation, schema validation, scenario reconstruction for Nepal, and Neo4j free-tier fallback queries required for the finale build. All unit tests pass cleanly, and the repository is merged with `origin/main` on the `teammate` branch.

```
Overall Progress: [████████████████░░░░] ~75% Complete
• T4 (Nepal Scenario Pack): 100% DONE
• T3 (Neo4j Checks & Cypher Queries): 100% DONE
• Setup & Conflict Resolution: 100% DONE
• T2 (South Fork 50 Road Crops): WAITING ON LEAD
• T1 (CAS Model Training & Weights): IN PROGRESS (Download & training scheduled before Thu 19 Nov 22:00 IST)
```

---

## 2. Work Completed

### A. Environment & Repository Synchronization
- Switched to `teammate` branch and merged latest `origin/main`.
- Resolved merge conflict in `docs/AI_DISCLOSURE.md` cleanly without overwriting historical logs.
- Synchronized dependencies with `uv sync`.
- Full project test suite passed: **107 passed, 1 skipped**.

### B. T4 — Nepal Flash Flood Scenario Pack (26 August 2026)
- **Script Created:** `scripts/prefetch_nepal.py` with offline fallback fixture and auto-environment delegation.
- **Corridor Covered:**
  - Prithvi Highway: Malekhu $\leftrightarrow$ Galchhi Base $\leftrightarrow$ Baireni
  - Dhading Link: Malekhu $\leftrightarrow$ Dhadingbesi
  - Pasang Lhamu Highway: Galchhi $\leftrightarrow$ Bidur / Trishuli Bazar $\leftrightarrow$ Betrawati $\leftrightarrow$ Dhunche $\leftrightarrow$ Syabrubesi $\leftrightarrow$ Rasuwagadhi (China border)
- **Reconstructed Disaster States (from cited reports):**
  - Trishuli River Bridge at Trishuli Bazar: swept away (`blocked`).
  - Phurke Khola Bridge at Malekhu: washed away (`blocked`).
  - Upper Mountain Highway (Betrawati to Rasuwagadhi): heavily damaged by landslides (`blocked` for ambulance/fire truck, `partial` for 4x4 jeep and foot).
  - Prithvi Highway (Baireni–Mugling): reopened 29 Aug after 3-day closure (`open`).
- **Data & Citations Logged:**
  - Updated `docs/sources_teammate.md` (Section 5) with full URLs, dates, and <=15-word quotes from Kathmandu Post (29 Aug 2026) and UN News (31 Aug 2026).
  - Attached authentic 2021 Nepal Census population figures (Bidur: 59,227; Dhadingbesi: 58,828; Galchhi: 27,784; Betrawati: 8,255; Dhunche: 7,143; etc.).
  - Added Nepal dataset and census rows to `data/LICENSES.md`.
- **Generated Outputs:**
  - `data/projects/nepal/roads/segments.geojson` (validates against `contracts/segments.schema.json`)
  - `data/projects/nepal/places.geojson` (validates against `contracts/places.schema.json`)
  - `data/projects/nepal/scenario_sources.json`
  - `data/projects/nepal/nepal_osm.gpkg` and `data/nepal_flood_corridor.gpkg`
- **Automated Verification:** Added `tests/test_advisor_nepal.py`, verifying schema compliance, advisor state assessment, and NetworkX reachability solvers.

### C. T3 — Neo4j AuraDB Free-Tier Investigation & Cypher Fallbacks
- **AuraDB Finding:** Confirmed that free hosted Neo4j AuraDB instances **do not include the Graph Data Science (GDS) plugin** (`gds.allShortestPaths.dijkstra` fails with procedure not found).
- **Pure Cypher Queries Authored & Tested (No Plugins Required):**
  1. **Reach:** Identifies settlements reachable by vehicle mode from the logistics staging base along open/partial roads.
  2. **Clear First:** Reopening priority ranking — identifies Trishuli Bazar Bridge (`seg_NEPAL_0006`) as Rank 1 (reconnects 59,227 people) and Phurke Khola Bridge (`seg_NEPAL_0003`) as Rank 2 (reconnects 58,828 people). Identical output to the NetworkX solver.
  3. **Fly Next:** Ranks unknown roads by the population whose route depends on them.
- All three queries are documented with full Cypher code in the report.

### D. Groundwork Report Authored
- Comprehensive handoff report written to `docs/teammate_finale_report.md` adhering strictly to all hard rules (no invented numbers, unrun items marked `PENDING`).

---

## 3. Work Left / Pending

### A. T1 — Model Training & Weights Export (Groundwork Task (Target: Before Thu 19 Nov 22:00 IST per Lead Instruction))
- **Dataset Download:** Download the 9.2 GB CAS Landslide Dataset (Zenodo 10294997), keeping only the drone (UAV) subsets.
- **Model Training:** Train a lightweight binary segmentation model (debris vs. clear) with a small backbone (e.g., ResNet-18) on laptop GPU (RTX 4050 6 GB) or CPU.
- **Held-out Evaluation:** Run evaluation on the designated held-out region (Bijie flight block) to record real IoU, precision, and recall.
- **Export & Timing:** Export model to ONNX (`.onnx`), measure 512x512 tile inference latency on CPU and GPU, and log the weights file SHA-256 checksum in the report.
- *Current status:* Set to `PENDING` in the report as per Hard Rule 1.

### B. T2 — South Fork 50 Road Crops Evaluation
- **Waiting on Lead:** The lead's side is scheduled to provide ~50 road crops from the South Fork map.
- **Action Required:** Label the 50 crops jointly ("debris on road" vs. "clear"), run the model, and report precision and recall separately from the held-out dataset.

### C. Finale Features Build (Sat 21 Nov 14:00 – Sun 22 Nov 12:00 at IIIT Delhi)
- **F3 (Debris on Roads):** Wire the trained ONNX model to evaluate the 498 South Fork road segments so they no longer read "unknown".
- **F4 (The Answer & The Plan in Neo4j):** Implement the Cypher queries and live graph updates into `advisor/` and the UI dashboard during the 22-hour hackathon hack window.

---

## 4. Deliverables Checklist for the Lead (Section 6)

| Field | Value |
|---|---|
| **Branch name** | `teammate` |
| **Commit hash** | `6e8c9cd` (clean commit; do not push without lead's approval) |
| **`pytest` summary** | `107 passed, 1 skipped, 18 warnings in 44.62s` |
| **Report location** | `docs/teammate_finale_report.md` |
| **Weights file** | `PENDING` (dataset download & training scheduled for compute slot) |
| **Impossible / Blocked** | Hosted AuraDB free-tier lacks GDS plugin; resolved with pure Cypher fallback queries. |
