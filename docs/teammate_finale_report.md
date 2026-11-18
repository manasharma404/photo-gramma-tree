# Teammate Finale Groundwork Report (17–19 Nov 2026)

**Project:** Project Typhon (Team Vortex)  
**Hackathon:** hackFront PS T8.2 "The First Map After The Landslide" (IIIT Delhi Finale)  
**Branch:** `teammate` (ahead of origin/teammate; merged with `origin/main`)  
**Test status:** `107 passed, 1 skipped, 18 warnings in 44.62s` (`uv run pytest -q`)

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
- Our South Fork drone orthomosaic resolution: **5–10 cm / pixel** (GSD).
- Target training resolution for CAS Landslide drone crops: **0.10 m / pixel (10 cm / px)**.
- Input prediction tiles are resized to $512 \times 512$ at 10 cm/pixel GSD.

### 2.2 Split & Hold-out Region
- **Held-out Region:** The Bijie (Guizhou) drone flight block is held out completely as the test set prior to training.
- **Training / Validation:** Remaining UAV subsets from Sichuan and Yunnan.

### 2.3 Proposed Rule: Debris Mask to `ml_scores.json` Contract
To keep the contract (`contracts/ml_scores.schema.json`: `p_blocked`, `p_partial`, `p_clear`, `model`, `version`), the model output per road segment corridor is mapped via the following proposed geometric rule:
$$\text{corridor\_debris\_fraction} = \frac{\text{Area of predicted debris within road polygon}}{\text{Total road corridor polygon area}}$$
$$\text{max\_debris\_depth\_m} = \text{maximum local elevation rise over road baseline}$$

- **Clear:** $\text{debris\_fraction} < 0.15 \implies p_{\text{clear}} = 1.0 - \text{debris\_fraction}, p_{\text{blocked}} = 0.0, p_{\text{partial}} = \text{debris\_fraction}$
- **Partial (crawl passable for 4x4 / foot):** $0.15 \le \text{debris\_fraction} < 0.60$ and $\text{clear\_width} \ge 2.2\,\text{m}$
- **Blocked:** $\text{debris\_fraction} \ge 0.60$ or $\text{clear\_width} < 1.0\,\text{m} \implies p_{\text{blocked}} \ge 0.85$

### 2.4 Benchmark Scores Table

| Evaluation Set | Model | IoU (Debris) | Precision | Recall | Status / Notes |
|---|---|---|---|---|---|
| **Held-out UAV Region (Bijie)** | Small U-Net (ResNet-18 backbone, ImageNet pretrain) | `PENDING` | `PENDING` | `PENDING` | Model training scheduled in finale compute slot |
| **Held-out UAV Region (Bijie)** | CRASAR-U-DROIDs VanillaUNet | Not compared | Not compared | Not compared | CRASAR weights expect 4-channel `(RGB + mask)` trained specifically on flood water, not rock/soil landslide debris |
| **South Fork 50 Road Crops** | Typhon Debris Segmenter | `PENDING` | `PENDING` | `PENDING` | Road crops to be labeled jointly with lead (T2) |

### 2.5 Inference Timing & Checksum
- **Inference Timing (512x512 tile):**
  - CPU (Intel Core i7 / AMD): `PENDING` ms
  - GPU (RTX 4050 Laptop 6 GB): `PENDING` ms
- **Weights File:** `PENDING` (will reside locally outside git; SHA-256 will be logged before commit).

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
- **Galchhi Rural Municipality:** 27,784 (National Population and Housing Census 2021, National Statistics Office Nepal)
- **Uttargaya (Betrawati) Rural Municipality:** 8,255 (National Population and Housing Census 2021, National Statistics Office Nepal)
- **Gosaikunda (Dhunche) Rural Municipality:** 7,143 (National Population and Housing Census 2021, National Statistics Office Nepal)
- **Baireni, Malekhu, Syabrubesi, Rasuwagadhi:** Set to null (sub-ward settlements and border checkpoints without standalone 2021 census municipal table; Hard Rule 1: no invented numbers)

### 4.3 Limits & Integrity Disclaimers
1. **Reconstruction, not drone measurement:** This scenario is reconstructed strictly from cited reports (Kathmandu Post 29 Aug 2026; UN News 31 Aug 2026; Nepal Census 2021) and is explicitly labelled `scenario reconstructed from reports, not drone-measured` on every segment and place feature.
2. **Post-disaster repairs:** Current OpenStreetMap data may reflect recent reconstruction; road states reflect the conditions reported between 26 and 31 August 2026.
3. **No casualty exploitation:** Casualties (903 dead, >4,200 missing cited by UN on 31 Aug 2026) are documented only as background context in sources; they are never used as a product feature or pitch hook.
4. **Offline availability:** The full dataset (`data/projects/nepal/`) loads offline through the exact same loader as Wayanad.

---

## 5. Summary of `PENDING` Items for Finale Slot
- [ ] Model weights training on CAS Landslide dataset (requires full dataset download and training on GPU during the finale build).
- [ ] Joint labeling of the 50 South Fork road crops with the lead.
- [ ] Final IoU/Precision/Recall numbers to replace `PENDING` placeholders.
- [ ] Model weights SHA-256 checksum and ONNX export.
