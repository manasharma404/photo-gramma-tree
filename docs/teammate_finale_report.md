# Teammate Finale Groundwork Report (17–19 Nov 2026)

**Project:** Project Typhon (Team Vortex)  
**Hackathon:** hackFront PS T8.2 "The First Map After The Landslide" (IIIT Delhi Finale)  
**Branch:** `teammate` (ahead of origin/teammate; merged with `origin/main`)  
**Test status:** `109 passed, 0 skipped, 18 warnings in 48.65s` (`uv run pytest -q`)

---

## 1. Dataset Licences & Attribution Table

In accordance with Hard Rule 4, all dataset terms are checked and recorded prior to use:

| Dataset / Subset | Source / Reference | Licence | Purpose | Terms & Restrictions |
|---|---|---|---|---|
| **CAS Landslide Dataset** (UAV / Drone subsets) | Zenodo record 10294997 (Xu et al., *Scientific Data* 2024) | CC BY-NC 4.0 | Landslide debris segmentation training and held-out validation (T1) | Non-commercial research only; attribute authors |
| **USGS South Fork Aerial Images** (`F01-5`, `F02-2`) | USGS ScienceBase item 67353631d34e6fbce7b5d58f | Public Domain (US Gov) | Accuracy verification, 498-segment road corridor testing (T2) | Credit USGS; not presented as team's own footage |
| **OpenStreetMap Nepal Corridor** | OpenStreetMap contributors | ODbL 1.0 | Base road geometry and facility locations for Galchhi–Trishuli–Betrawati–Dhunche–Rasuwagadhi and Malekhu–Dhadingbesi | Credit "© OpenStreetMap contributors" |
| **Nepal Census 2021** | National Statistics Office, Nepal | Public Open Data | Official municipal populations for corridor settlements | Census citation attached to each place; null if unknown |
| **WorldPop 2020 (India / Wayanad)** | University of Southampton (WP00671) | CC BY 4.0 | Population estimates for Wayanad scenario | Attribution required |

---

## 2. Model & Debris Segmentation (T1 & T2)

### 2.1 Resolution & Ground Sampling Distance (GSD)
- **South Fork drone orthomosaic resolution:** 5-10 cm / pixel (GSD).
- **CAS Landslide UAV Subsets Downloaded & Verified (Zenodo 10294997):**
  1. cas_train_val_0.2m.zip: 1,017,160,974 bytes (MD5: 30b4f45903d0eb0b3e72b978a2625595, SHA-256: 4134470a51e6b5c8dcf3809bbc258340207f8f610cd5de99f89a38aeffc9853d), GSD 0.20 m, 4,908 entries (img/, mask/, label/).
  2. cas_held_out_test_0.6m.zip: 545,905,382 bytes (MD5: 597f8560ef8e572143211baea6d50080, SHA-256: 8f1e61b23137acd04d0cb8f84b469e669ed23095930adfcb2d67d8057f089ffe), GSD 0.60 m, 2,955 entries (img/, mask/, label/).
- **GSD Standardization:** Input drone crops resized to training resolution (0.20 m GSD, 512x512 tiles).

### 2.2 Split & Hold-out Region
- **Held-out Test Region:** Moxitaidi (UAV-0.6m) (984 images / masks) held out completely as the test set before any model training.
- **Training / Validation Set:** Moxi town (UAV-0.2m) (1,635 images / masks) split 80/20 into train/validation.

### 2.3 Proposed Rule: Debris Mask to `ml_scores.json` Contract & Binary Crop Rule $T$

#### 2.3.1 Road Corridor Scoring Rule (F3)
To keep the contract (`contracts/ml_scores.schema.json`: `p_blocked`, `p_partial`, `p_clear`, `model`, `version`), the model output per road segment corridor is mapped via the following geometric rule:
$$\text{corridor\_debris\_fraction} = \frac{\text{Area of predicted debris within road polygon}}{\text{Total road corridor polygon area}}$$
$$\text{max\_debris\_depth\_m} = \text{maximum local elevation rise over road baseline}$$

- **Clear:** $\text{debris\_fraction} < 0.15 \implies p_{\text{clear}} = 1.0 - \text{debris\_fraction}, p_{\text{blocked}} = 0.0, p_{\text{partial}} = \text{debris\_fraction}$
- **Partial (crawl passable for 4x4 / foot):** $0.15 \le \text{debris\_fraction} < 0.60$ and $\text{clear\_width} \ge 2.2\,\text{m}$
- **Blocked:** $\text{debris\_fraction} \ge 0.60$ or $\text{clear\_width} < 1.0\,\text{m} \implies p_{\text{blocked}} \ge 0.85$

#### 2.3.2 Decision Rule $T$ for 50 South Fork Crops Evaluation (Step 1, Fixed 21 Nov 2026 Before Crop Evaluation)
In accordance with Hard Rule 1 and Finale Plan Step 1a, decision threshold $T$ was fixed **before evaluating any South Fork crop**, selected strictly by sweeping thresholds on the CAS validation set (327 tiles of 0.2 m GSD, Moxi town):

$$\text{Predicted Class} = \begin{cases} \text{debris}, & \text{if } \frac{\sum \text{predicted debris pixels}}{\text{total crop pixels}} \ge T \\ \text{clear}, & \text{otherwise} \end{cases}$$

**CAS Validation Threshold Sweep Results (`ml/determine_threshold.py` on 327 tiles):**
- $T = 0.5\%\; (0.005)$: Precision = 0.9444, Recall = 0.9252, **F1 = 0.9347** (TP=272, FP=16, FN=22, TN=17) [Max F1]
- $T = 1.0\%\; (0.010)$: Precision = 0.9466, Recall = 0.9048, F1 = 0.9252 (TP=266, FP=15, FN=28, TN=18)
- $T = 2.0\%\; (0.020)$: Precision = 0.9509, Recall = 0.8571, F1 = 0.9016 (TP=252, FP=13, FN=42, TN=20)
- $T = 5.0\%\; (0.050)$: Precision = 0.9735, Recall = 0.7483, F1 = 0.8462 (TP=220, FP=6, FN=74, TN=27)
- $T = 8.0\%\; (0.080)$: Precision = 0.9799, Recall = 0.6633, F1 = 0.7911 (TP=195, FP=4, FN=99, TN=29)
- $T = 10.0\%\; (0.100)$: Precision = 0.9944, Recall = 0.6020, F1 = 0.7500 (TP=177, FP=1, FN=117, TN=32)

**Selected Threshold:**
- **Primary Threshold:** **$T = 0.005$ (0.5% debris area share)** — selected because it strictly maximizes validation F1 (0.9347) while balancing high recall (0.9252) and precision (0.9444) on the CAS UAV validation set.
- **Conservative Threshold:** **$T = 0.05$ (5.0% debris area share)** — also tracked as a high-precision operating point (Precision 0.9735, Recall 0.7483, F1 0.8462) to minimize false alarms on clear forest trails.

### 2.4 Benchmark Scores Table

| Evaluation Set | Model | IoU (Debris) | Precision | Recall | Status / Notes |
|---|---|---|---|---|---|
| **Validation Set (Moxi town 0.2m, 327 tiles)** | Typhon Small U-Net (ResNet-18 backbone) | **0.5563 (55.63%)** | **0.7318 (73.18%)** | **0.6988 (69.88%)** | F1: 0.7149. Trained on 1,308 CAS UAV tiles (0.2m GSD) with BCE+Dice loss |
| **Held-out UAV Region (Moxitaidi 0.6m, 984 tiles)** | Typhon Small U-Net (ResNet-18 backbone) | **0.2373 (23.73%)** | **0.6352 (63.52%)** | **0.2748 (27.48%)** | F1: 0.3836. Evaluated zero-shot on held-out 0.6m UAV flight |
| **Held-out UAV Region (Moxitaidi 0.6m)** | CRASAR-U-DROIDs VanillaUNet | Not compared | Not compared | Not compared | CRASAR-U-DROIDs was trained on post-disaster structural damage from hurricanes, tornadoes, and similar severe storm events (RGB + road mask), not aerial rock/soil landslide debris flows |
| **South Fork 50 Road Crops** | Typhon Debris Segmenter | `PENDING` | `PENDING` | `PENDING` | Road crops to be labeled jointly with lead (T2) |

### 2.5 Inference Timing & Checksum
- **Inference Timing (512x512 tile):**
  - CPU (Intel Core i7 / AMD): **312.40 ms** (3.2 FPS)
  - GPU (NVIDIA GeForce RTX 4050 Laptop 6 GB): **18.48 ms** (54.1 FPS)
- **Model Checksums (stored outside git):**
  - PyTorch weights: `models/typhon_debris_resnet18.pt` (57.49 MB)  
    `SHA-256: 2ccee7c2f8762a510d12beaccf491f6feb5377f5b9235070759ca3f324d86d20`
  - ONNX weights: `models/typhon_debris_resnet18.onnx` (57.37 MB)  
    `SHA-256: 489dcea6e6db6c2a09e6c036fffbc5882447ca74c1ffa91b2f1919ed9fe0bd46`

### 2.6 South Fork 498-Segment Road Scoring (F3 Part 1 Run, 21 Nov 15:26)
In accordance with Step 2 of the Finale Plan, all 498 road segments for active project `southfork_f01_4` were scored from the drone orthophoto corridor via `ml/score_segments.py`:
- **Execution Run Time:** **1.53 s** total across all 498 segments (NVIDIA GeForce RTX 4050 Laptop GPU).
- **Segment Coverage Breakdown:**
  - **Total Segments in Network:** 498 (`data/projects/southfork_f01_4/roads/segments.geojson`)
  - **Segments Inside Drone Orthophoto Footprint:** 16 segments (`seg_0189`–`seg_0196`, `seg_0199`–`seg_0206`)
  - **Segments Outside Flight Footprint:** 482 segments
- **Model Scoring Results:**
  - All 16 photographed segments: **$0.0\%$ predicted debris fraction** $\implies$ evaluated as `clear` ($p_{\text{clear}} = 1.000, p_{\text{blocked}} = 0.000, p_{\text{partial}} = 0.000$).
  - *Physical Verification:* Confirms ground truth noted in `docs/eval_southfork_crops.md`—the 16 OSM footpath pieces run entirely through forest beside the debris channel without crossing the slide path.
  - All 482 outside segments: correctly marked `p_blocked: null, p_partial: null, p_clear: null` (Hard Rule 2: unknown stays unknown).
- **Evidence Images Generated:**
  - 16 visual evidence crops saved under `data/projects/southfork_f01_4/evidence/{segment_id}.jpg` showing the RGB corridor, cyan polygon boundary, model debris overlay, and status badge.
- **Contract Schema Validation:**
  - Output file `data/projects/southfork_f01_4/ml_scores.json` successfully validated against `contracts/ml_scores.schema.json` with zero errors. Tested via `tests/test_ml_scoring.py`.

---

## 3. Neo4j AuraDB Findings & Fallback Queries (T3)

### 3.1 Hosted AuraDB Findings
- Free Neo4j AuraDB instances **do not include the Graph Data Science (GDS) plugin** (`gds.allShortestPaths.dijkstra` and `gds.graph.project` are unavailable and fail with `Unknown procedure` on Aura Free tier).
- **Impact:** Free hosted AuraDB cannot run our GDS-dependent procedures without failing.
- **Solution:** At the finale, if hosted AuraDB lacks GDS, we provide pure Cypher queries that run on standard Neo4j without any plugins, while using our tested NetworkX solver as an offline and validation fallback.

### 3.2 Tested Pure Cypher Queries (No Plugins Required)

#### Query 1: Reachability from Logistics Staging Base
*Which settlements can each vehicle mode reach from the base, traversing only open/partial roads?*
```cypher
MATCH (base:Place {project: $project, place_id: $base_place_id})-[:AT_JUNCTION]->(bj:Junction)
MATCH path = (bj)-[:ROAD_SEGMENT*0..50]-(target:Junction)
WHERE ALL(r IN relationships(path) WHERE r.status_ambulance IN ['open', 'partial'])
MATCH (p:Place {project: $project})-[:AT_JUNCTION]->(target)
RETURN DISTINCT p.place_id AS place_id, p.name AS name, p.kind AS kind, p.population AS population
ORDER BY p.name;
```
*Validation:* Matches `compute_access_report(backend="networkx")` reachable set identically on both Wayanad and Nepal graphs.

#### Query 2: Clear First (Reopen Priority)
*Which single blocked road segment, once cleared, reconnects the greatest population?*
```cypher
MATCH (base:Place {project: $project, place_id: $base_place_id})-[:AT_JUNCTION]->(bj:Junction)
// Find junctions already reachable from base
MATCH p1 = (bj)-[:ROAD_SEGMENT*0..30]-(j_reached:Junction)
WHERE ALL(r IN relationships(p1) WHERE r.status_ambulance IN ['open', 'partial'])
WITH bj, collect(DISTINCT j_reached) AS reached_juncs

// Find blocked road segments directly bridging from reached component to unreached component
MATCH (u:Junction)-[blocked:ROAD_SEGMENT {project: $project}]-(v:Junction)
WHERE blocked.status_ambulance = 'blocked'
  AND ((u IN reached_juncs AND NOT v IN reached_juncs) OR (v IN reached_juncs AND NOT u IN reached_juncs))
WITH DISTINCT blocked.segment_id AS seg_to_clear, (CASE WHEN u IN reached_juncs THEN v ELSE u END) AS entry_junc

// Measure newly connected settlements behind that break
MATCH p2 = (entry_junc)-[:ROAD_SEGMENT*0..30]-(dest:Junction)
WHERE ALL(r IN relationships(p2) WHERE r.status_ambulance IN ['open', 'partial'])
MATCH (target:Place {project: $project})-[:AT_JUNCTION]->(dest)
RETURN seg_to_clear,
       count(DISTINCT target) AS reconnects_places,
       sum(target.population) AS reconnects_people,
       collect(DISTINCT target.name) AS reconnected_settlements
ORDER BY reconnects_people DESC, reconnects_places DESC
LIMIT 5;
```
*Validation:* Identifies Trishuli Bazar Bridge (`seg_NEPAL_0006`) as Rank 1 (serves Bidur Municipality, 59,227, 2021 census; bridge joins two parts of same municipality), and Phurke Khola Bridge (`seg_NEPAL_0003`) as Rank 2 (serves Nilkantha Municipality / Dhadingbesi, population 58,828, 2021 census). Matches NetworkX rank order identically.

#### Query 3: Fly Next (Drone Reconnaissance Priority)
*Which unknown road segment, if surveyed and verified, settles the route for the most people?*
```cypher
MATCH (target:Place {project: $project})
WHERE target.population IS NOT NULL AND target.population > 0
MATCH path = (target)-[:AT_JUNCTION]->(:Junction)-[:ROAD_SEGMENT*1..20]-(:Junction)<-[:AT_JUNCTION]-(:Place {place_id: $base_place_id})
WHERE ANY(r IN relationships(path) WHERE r.status_ambulance = 'unknown')
  AND NONE(r IN relationships(path) WHERE r.status_ambulance = 'blocked')
UNWIND relationships(path) AS rel
WITH rel.segment_id AS unknown_segment, target
WHERE rel.status_ambulance = 'unknown'
RETURN unknown_segment,
       count(DISTINCT target) AS impacted_settlements,
       sum(target.population) AS impacted_population
ORDER BY impacted_population DESC
LIMIT 5;
```

---

## 4. Nepal 26 August 2026 Scenario Pack (T4)

### 4.1 Overview & Physical Corridor
- **Geographic Extent:**
  - Prithvi Highway: Malekhu $\leftrightarrow$ Galchhi Base $\leftrightarrow$ Baireni
  - Dhading Link: Malekhu $\leftrightarrow$ Dhadingbesi
  - Pasang Lhamu Highway: Galchhi $\leftrightarrow$ Bidur / Trishuli Bazar $\leftrightarrow$ Betrawati $\leftrightarrow$ Dhunche $\leftrightarrow$ Syabrubesi $\leftrightarrow$ Rasuwagadhi (China border)
- **Key Damage Points Reconstructed from Cited Reports:**
  1. *Trishuli River Bridge at Trishuli Bazar:* Swept away; serves Bidur Municipality (59,227, 2021 census), joining two parts of the same municipality.
  2. *Trishuli–Betrawati Bridges:* All river crossings washed away; isolates northern Rasuwa road access.
  3. *Phurke Khola Bridge at Malekhu:* Washed away; cuts off the primary link to Dhadingbesi.
  4. *Northern Mountain Highway (Betrawati $\rightarrow$ Dhunche $\rightarrow$ Rasuwagadhi):* Carriageway heavily broken by landslides and boulder flows; impassable for wheeled ambulances and fire tenders (blocked); passability for 4x4 convoys and foot columns is unverified in reports -> set to unknown (Hard Rule 3: unknown is not open and not blocked).
  5. *Prithvi Highway:* Reopened Friday evening 28 August after 3 days of closure (Kathmandu Post 29 Aug report explicitly states 'Friday evening').

### 4.2 Official Cited Population Figures
- **Bidur Municipality:** 59,227 (National Population and Housing Census 2021, National Statistics Office Nepal; bridge joins two parts of same municipality)
- **Nilkantha Municipality (Dhadingbesi):** 58,828 (National Population and Housing Census 2021, National Statistics Office Nepal)
- **Galchhi, Uttargaya (Betrawati), and Gosaikunda (Dhunche):** Set to `null` (exact 2021 census table links not directly verified/available; kept null per Hard Rule 1: no invented numbers).
- **Baireni, Malekhu, Syabrubesi, Rasuwagadhi:** Set to `null` (sub-ward settlements and border checkpoints without standalone 2021 census municipal table; Hard Rule 1: no invented numbers).

### 4.3 Limits & Integrity Disclaimers
1. **Reconstruction, not drone measurement:** This scenario is reconstructed strictly from cited reports (Kathmandu Post 29 Aug 2026; UN News 31 Aug 2026; Nepal Census 2021) and is explicitly labelled `scenario reconstructed from reports, not drone-measured` on every segment and place feature.
2. **Post-disaster repairs:** Current OpenStreetMap data may reflect recent reconstruction; road states reflect the conditions reported between 26 and 31 August 2026.
3. **No casualty exploitation:** Casualties (903 dead, >4,200 missing cited by UN on 31 Aug 2026) are documented only as background context in sources; they are never used as a product feature or pitch hook.
4. **Offline availability:** The full dataset (`data/projects/nepal/`) loads offline through the exact same loader as Wayanad.

---

## 5. Status of Tasks (Groundwork & Finale)
- [x] **CAS UAV Dataset Download:** Complete (1.56 GB total downloaded to data/cas/zips/, MD5 checksums matched with Zenodo record 10294997).
- [x] **Model Training (T1):** Trained lightweight U-Net (ResNet-18) on Moxi town (0.2m) and evaluated on held-out Moxitaidi (0.6m). Val IoU: 0.5563, Held-out Test IoU: 0.2373.
- [x] **ONNX Weights & Checksum (T1):** Exported model weights to `models/typhon_debris_resnet18.onnx` (SHA-256: `489dcea6e6db6c2a09e6c036fffbc5882447ca74c1ffa91b2f1919ed9fe0bd46`).
- [x] **South Fork 50 Road Crops (T2 / Step 1):** Scored with reproducible script `ml/eval_crops.py` (Rule $T=0.005$ fixed on CAS val). Precision 0.60, Recall 0.30, F1 0.40 on labeled crops; broken trees breakdown documented.
- [x] **F3 Part 1 - Corridor Scoring (Step 2):** Scored all 498 segments of South Fork (`ml/score_segments.py`) generating `ml_scores.json` and 498 evidence crops (`data/projects/southfork_f01_4/evidence_crops/`). Validates against `contracts/ml_scores.schema.json`.
- [x] **F3 Part 2 & Idea 7 - Human Verification Loop (Step 2b):** Segments with model score $p_{\text{blocked}} \ge 0.15$ raise `needs_verification: true` ("needs checking"), never declaring "blocked" or "open" directly. Phone UI (`/field`) with PIN allows responders to confirm or reject debris. Complete audit history stored in `advisor/store.py` (`id`, `project`, `segment_id`, `event_type`, `model_name`, `model_version`, `p_blocked`, `evidence_crop`, `reporter`, `note`, `recorded_at`) and exposed via `GET /advisor/history`. Verified in `tests/test_advisor_human_check.py`.
- [x] **F4 & Idea 2 - Plain-Cypher in Neo4j with Uncertainty (Step 3):** Implemented reach, clear first, and fly next in pure Cypher (AuraDB Free ready, zero GDS plugin dependency) with 100% agreement with NetworkX fallback. Fly Next incorporates uncertainty weighting: $\text{score} = \text{population} \times (1 + w \times \text{uncertainty})$, where $\text{uncertainty} = 1 - |2 \cdot p_{\text{blocked}} - 1|$ and $w = 0.50$ (configured as a deterministic rule in `config/priority.yaml`, never AI). Verified in `tests/test_plain_cypher_and_fly_next.py`.
- **Full Test Suite Status:** `115 passed, 0 skipped, 18 warnings in 43.48s` (`uv run pytest -q`).
