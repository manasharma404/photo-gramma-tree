# Teammate Source & Placeholder Register (`S1`)

Every numeric parameter in `config/vehicles.yaml` and `config/priority.yaml`, every reconstructed road state in `scripts/prefetch_wayanad.py`, and every external dataset/model used in teammate modules either cites a specific document URL opened and read firsthand or is explicitly marked `PLACEHOLDER` with the reason. No bare domain/home-page citations are permitted.

## 1. Vehicle Passability Profiles (`config/vehicles.yaml`)

| Parameter | Value | URL or `PLACEHOLDER` | Date | What It Says (<=15-word quote or paraphrase) | Licence / Terms |
| --- | --- | --- | --- | --- | --- |
| `assessment_rules.min_coverage_fraction` | `0.70` | `PLACEHOLDER` | 2026-10-31 | Operational rule: minimum valid DSM pixel fraction over road corridor before declaring passability. | N/A (`PLACEHOLDER`) |
| `assessment_rules.default_width_tolerance_m` | `0.20` | `PLACEHOLDER` | 2026-10-31 | Operational rule: fallback horizontal clear-width tolerance when segment `RMSE_H` is unavailable. | N/A (`PLACEHOLDER`) |
| `assessment_rules.default_height_tolerance_m` | `0.04` | `PLACEHOLDER` | 2026-10-31 | Operational rule: fallback vertical local surface-fit obstruction tolerance when DSM tolerance is absent. | N/A (`PLACEHOLDER`) |
| `assessment_rules.ml_disagreement_p_blocked` | `0.60` | `PLACEHOLDER` | 2026-10-31 | Operational rule: flag `needs_verification: true` when pre-trained model `p_blocked >= 0.60` on open/partial geometry. | N/A (`PLACEHOLDER`) |
| `fire_truck.width_m` | `2.50` | https://archive.org/download/gov.in.is.950.2012/is.950.2012.pdf | Oct 2012 (retrieved 2026-10-31) | IS 950:2012 Clause 3.2(f), p. 1: `"Overall width: Not more than 2.50 m"`. | BIS public safety standard |
| `fire_truck.height_m` | `3.60` | `PLACEHOLDER` | 2026-10-31 | IS 950:2012 Clause 3.2(f) omits overall appliance height; calibrate against responder tender registration certificate. | N/A (`PLACEHOLDER`) |
| `fire_truck.ground_clearance_m` | `0.23` | https://archive.org/download/gov.in.is.950.2012/is.950.2012.pdf | Oct 2012 (retrieved 2026-10-31) | IS 950:2012 Clause 3.2(f), p. 1: `"Road clearance: Not less than 230 mm"`. | BIS public safety standard |
| `fire_truck.overhead_clearance_margin_m` | `0.90` | `PLACEHOLDER` | 2026-10-31 | Vertical buffer above fire tender roof/gallows; kept `PLACEHOLDER` because appliance height is `PLACEHOLDER`. | N/A (`PLACEHOLDER`) |
| `fire_truck.clearance_per_side_m` | `0.50` | `PLACEHOLDER` | 2026-10-31 | Operational lateral buffer per side (`3.50 m` clear single-file emergency transit lane). | N/A (`PLACEHOLDER`) |
| `fire_truck.partial_clearance_per_side_m` | `0.20` | `PLACEHOLDER` | 2026-10-31 | Operational tight crawl lateral buffer per side (`2.90 m` escorted crawl width). | N/A (`PLACEHOLDER`) |
| `fire_truck.max_obstruction_open_m` | `0.12` | `PLACEHOLDER` | 2026-10-31 | Operational threshold (~50% of `0.23 m` IS 950 road clearance) for unobstructed transit. | N/A (`PLACEHOLDER`) |
| `fire_truck.max_obstruction_partial_m` | `0.22` | `PLACEHOLDER` | 2026-10-31 | Operational crawl limit just below `0.23 m` IS 950 road clearance with spotter. | N/A (`PLACEHOLDER`) |
| `fire_truck.max_obstructed_length_partial_m` | `10.0` | `PLACEHOLDER` | 2026-10-31 | Operational maximum continuous rough-debris length (`10 m`) passable by fire tender at crawl. | N/A (`PLACEHOLDER`) |
| `ambulance.width_m` | `1.925` | https://www.forcemotors.com/vehicles/traveller-ambulance-3350wb-c-type/ | Retrieved 2026-10-31 | Technical Specifications -> Dimensions (mm) table: `"Overall Width 1925"` (`1.925 m`). | Manufacturer public spec |
| `ambulance.height_m` | `2.615` | https://www.forcemotors.com/vehicles/traveller-ambulance-3350wb-c-type/ | Retrieved 2026-10-31 | Technical Specifications -> Dimensions (mm) table: `"Overall Height 2615"` (`2.615 m`). | Manufacturer public spec |
| `ambulance.ground_clearance_m` | `0.20` | https://www.forcemotors.com/vehicles/traveller-ambulance-3350wb-c-type/ | Retrieved 2026-10-31 | Technical Specifications -> Dimensions (mm) table: `"Ground Clearance 200"` (`0.20 m`). | Manufacturer public spec |
| `ambulance.overhead_clearance_margin_m` | `0.30` | `PLACEHOLDER` | 2026-10-31 | Operational vertical clearance margin above `2.615 m` ambulance roof. | N/A (`PLACEHOLDER`) |
| `ambulance.clearance_per_side_m` | `0.35` | `PLACEHOLDER` | 2026-10-31 | Operational lateral buffer per side (`2.625 m` normal clear ambulance width). | N/A (`PLACEHOLDER`) |
| `ambulance.partial_clearance_per_side_m` | `0.15` | `PLACEHOLDER` | 2026-10-31 | Operational tight crawl buffer per side (`2.225 m` minimum ambulance crawl width). | N/A (`PLACEHOLDER`) |
| `ambulance.max_obstruction_open_m` | `0.10` | `PLACEHOLDER` | 2026-10-31 | Operational threshold (50% of `0.20 m` ground clearance) for smooth patient transport. | N/A (`PLACEHOLDER`) |
| `ambulance.max_obstruction_partial_m` | `0.18` | `PLACEHOLDER` | 2026-10-31 | Operational slow-crawl debris height limit below `0.20 m` ambulance ground clearance. | N/A (`PLACEHOLDER`) |
| `ambulance.max_obstructed_length_partial_m` | `8.0` | `PLACEHOLDER` | 2026-10-31 | Operational maximum continuous debris length (`8 m`) for partial ambulance crawl. | N/A (`PLACEHOLDER`) |
| `jeep.width_m` | `1.82` | `PLACEHOLDER` | 2026-10-31 | Representative 3-door 4WD SUV width; Mahindra Thar PDF brochure uses non-plain-text CID glyphs. | N/A (`PLACEHOLDER`) |
| `jeep.height_m` | `1.855` | `PLACEHOLDER` | 2026-10-31 | Representative 3-door 4WD SUV height; Mahindra Thar PDF brochure uses non-plain-text CID glyphs. | N/A (`PLACEHOLDER`) |
| `jeep.ground_clearance_m` | `0.226` | `PLACEHOLDER` | 2026-10-31 | Representative 3-door 4WD SUV clearance; Mahindra Thar PDF brochure uses non-plain-text CID glyphs. | N/A (`PLACEHOLDER`) |
| `jeep.overhead_clearance_margin_m` | `0.25` | `PLACEHOLDER` | 2026-10-31 | Operational vertical clearance buffer above 4WD utility roof. | N/A (`PLACEHOLDER`) |
| `jeep.clearance_per_side_m` | `0.30` | `PLACEHOLDER` | 2026-10-31 | Operational lateral buffer per side (`2.42 m` unobstructed 4WD lane width). | N/A (`PLACEHOLDER`) |
| `jeep.partial_clearance_per_side_m` | `0.15` | `PLACEHOLDER` | 2026-10-31 | Operational tight crawl buffer per side (`2.12 m` low-range 4WD crawl width). | N/A (`PLACEHOLDER`) |
| `jeep.max_obstruction_open_m` | `0.15` | `PLACEHOLDER` | 2026-10-31 | Operational unobstructed 4WD passability height below `0.226 m` ground clearance. | N/A (`PLACEHOLDER`) |
| `jeep.max_obstruction_partial_m` | `0.25` | `PLACEHOLDER` | 2026-10-31 | Operational low-range 4WD wheel-placement / straddle limit; verify on ground. | N/A (`PLACEHOLDER`) |
| `jeep.max_obstructed_length_partial_m` | `15.0` | `PLACEHOLDER` | 2026-10-31 | Operational maximum continuous rough-debris length (`15 m`) for partial 4WD crawl. | N/A (`PLACEHOLDER`) |
| `foot.width_m` | `0.60` | `PLACEHOLDER` | 2026-10-31 | Operational single responder shoulder/pack width (`0.60 m`). | N/A (`PLACEHOLDER`) |
| `foot.height_m` | `2.00` | `PLACEHOLDER` | 2026-10-31 | Operational upright responder headroom with helmet (`2.00 m`). | N/A (`PLACEHOLDER`) |
| `foot.ground_clearance_m` | `null` | `PLACEHOLDER` | 2026-10-31 | Not applicable to foot teams; governed by step-over and scramble height thresholds. | N/A (`PLACEHOLDER`) |
| `foot.overhead_clearance_margin_m` | `0.10` | `PLACEHOLDER` | 2026-10-31 | Operational helmet overhead clearance margin (`0.10 m`). | N/A (`PLACEHOLDER`) |
| `foot.clearance_per_side_m` | `0.20` | `PLACEHOLDER` | 2026-10-31 | Operational buffer (`1.00 m` total path) for two-person stretcher carry. | N/A (`PLACEHOLDER`) |
| `foot.partial_clearance_per_side_m` | `0.05` | `PLACEHOLDER` | 2026-10-31 | Operational buffer (`0.70 m` total path) for single-file unladen scramble. | N/A (`PLACEHOLDER`) |
| `foot.max_obstruction_open_m` | `0.35` | `PLACEHOLDER` | 2026-10-31 | Operational normal step-over obstacle height (`0.35 m`) without scrambling. | N/A (`PLACEHOLDER`) |
| `foot.max_obstruction_partial_m` | `1.20` | `PLACEHOLDER` | 2026-10-31 | Operational unassisted rubble scramble height limit (`1.20 m`) without rope/ladder. | N/A (`PLACEHOLDER`) |
| `foot.max_obstructed_length_partial_m` | `35.0` | `PLACEHOLDER` | 2026-10-31 | Operational maximum continuous debris scramble length (`35 m`) for foot teams. | N/A (`PLACEHOLDER`) |

## 2. Priority Decision-Support Weights (`config/priority.yaml`)

| Parameter | Value | URL or `PLACEHOLDER` | Date | What It Says (<=15-word quote or paraphrase) | Licence / Terms |
| --- | --- | --- | --- | --- | --- |
| `weights.access_difficulty` | `0.30` | `PLACEHOLDER` | 2026-10-31 | Hand-set decision-support weight for multi-vehicle isolation severity (not AI, not dispatch). | N/A (`PLACEHOLDER`) |
| `weights.damage_severity` | `0.25` | `PLACEHOLDER` | 2026-10-31 | Hand-set decision-support weight for blockage severity on nearest road segments. | N/A (`PLACEHOLDER`) |
| `weights.population_exposure` | `0.20` | `PLACEHOLDER` | 2026-10-31 | Hand-set decision-support weight for known population (`null` stays unknown, never `0`). | N/A (`PLACEHOLDER`) |
| `weights.critical_facilities` | `0.15` | `PLACEHOLDER` | 2026-10-31 | Hand-set decision-support weight for hospitals, shelters, schools, and landing zones. | N/A (`PLACEHOLDER`) |
| `weights.alternative_routes` | `0.10` | `PLACEHOLDER` | 2026-10-31 | Hand-set decision-support weight for lack of redundant edge-disjoint routes. | N/A (`PLACEHOLDER`) |
| `scaling.population_reference_max` | `250` | `PLACEHOLDER` | 2026-10-31 | Hand-set hill-hamlet reference population mapped to `100` on exposure scale. | N/A (`PLACEHOLDER`) |
| `scaling.level_thresholds.critical` | `75.0` | `PLACEHOLDER` | 2026-10-31 | Hand-set composite score cut-off for `critical` decision-support tier. | N/A (`PLACEHOLDER`) |
| `scaling.level_thresholds.high` | `50.0` | `PLACEHOLDER` | 2026-10-31 | Hand-set composite score cut-off for `high` decision-support tier. | N/A (`PLACEHOLDER`) |
| `scaling.level_thresholds.moderate` | `25.0` | `PLACEHOLDER` | 2026-10-31 | Hand-set composite score cut-off for `moderate` decision-support tier. | N/A (`PLACEHOLDER`) |

## 3. Wayanad Scenario Reconstruction (`scripts/prefetch_wayanad.py` & `scripts/prefetch_worldpop_wayanad.py`)

| Scenario Element / Road State | Assigned State | URL or `PLACEHOLDER` | Date | What It Says (<=15-word quote or paraphrase) | Licence / Terms |
| --- | --- | --- | --- | --- | --- |
| Base road network & place nodes (`11.472–11.512 N, 76.135–76.172 E`) | Geometry & POIs | https://www.openstreetmap.org/copyright | Retrieved 2026-10-31 | `"OpenStreetMap® is open data, licensed under the Open Data Commons Open Database License"` | ODbL 1.0 |
| Default corridor width by `highway` class when OSM `width` tag is missing | `1.5–7.0 m` | `PLACEHOLDER` | 2026-10-31 | Fallback corridor width by OSM highway class when `width` tag is absent. | N/A (`PLACEHOLDER`) |
| Rule 1: Chooralmala river bridge (`way/380928388`) | `blocked / blocked / blocked / blocked` | https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2041094 | 2024-08-03 (retrieved 2026-10-31) | Para 2: `"connecting the regions of Chooralmala and Mundakkai which were isolated by the landslides"` | GODL-India (PIB) |
| Rule 1 (corroborating): Chooralmala bridge site airlift requirement | `blocked` across stream | https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039494 | 2024-07-31 (retrieved 2026-10-31) | Actions Planned: `"construction of a bridge on the Meppadi-Chooralmala Road will commence"` | GODL-India (PIB) |
| Rule 2: Upper Punchirimattom–Mundakkai zone (`lat < 11.4855`) | `blocked / blocked / blocked / partial` | https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2041094 | 2024-08-03 (retrieved 2026-10-31) | Para 3: `"airlifted 12 state police personnel... to the disaster area, which were inaccessible by road."` | GODL-India (PIB) |
| Rule 2 & 3 (corroborating): Mundakkai, Chooralmala, Vellarimala damage | ~700 houses buried under debris | https://www.sphereindia.org.in/sites/default/files/2024-08/SI_Sitrep-5__Wayanad_Landslide_26-08-2024.pdf | 2024-08-26 (retrieved 2026-10-31) | Page 1: 30 July 2024 02:17 hrs landslide buried ~700 houses across Mundakkai, Chooralmala, Vellarimala. | Sphere India public SitRep |
| Rule 3: Southern bank Mundakkai–Vellarmala–Attamala roads (`11.4855 <= lat < 11.4995`) | `blocked / partial / partial / open` | https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2041094 | 2024-08-03 (retrieved 2026-10-31) | Para 2: `"enabling movement of heavy machinery and ambulances"` once Bailey bridge connected Mundakkai; `fire_truck=blocked` is `PLACEHOLDER`. | GODL-India (PIB) + `PLACEHOLDER` |
| Rule 4: Northern Meppadi–Chooralmala staging corridor (`way/30778557`, `lat >= 11.4990`) | `open / open / open / open` | https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039871 | 2024-07-31 (retrieved 2026-10-31) | Para 4 & 7: 150-ft Bailey bridge, three JCBs, and Kalpetta ambulances inducted via Meppadi–Chooralmala road. | GODL-India (PIB) |
| Rule 5: Minor unpaved `highway=track` inside 6 km landslide valley | `blocked / blocked / blocked / unknown` | https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2039871 | 2024-07-31 (retrieved 2026-10-31) | Para 2: `"operations along six kilometre stretch of landslide affected areas"`; minor track states are `PLACEHOLDER` (`foot=unknown`). | GODL-India (PIB) + `PLACEHOLDER` |
| Rule 6: Unreported peripheral minor tracks outside valley | `unknown / unknown / unknown / unknown` | `PLACEHOLDER` | 2026-10-31 | No post-landslide passability report found -> kept `unknown` (never assumed `open`). | N/A (`PLACEHOLDER`) |
| Wayanad settlement population (`C1`, `scripts/prefetch_worldpop_wayanad.py`) | Sum of 100 m cells within `500 m` radius (`null` for non-settlements) | https://hub.worldpop.org/geodata/summary?id=6527 | 2020 dataset (retrieved 2026-10-31) | WorldPop 2020 UN-adjusted constrained 100 m residential population counts for India (`DOI: 10.5258/SOTON/WP00645`). | CC BY 4.0 |
| Wayanad WorldPop GeoTIFF raster URL (`C1`) | `ind_ppp_2020_UNadj_constrained.tif` | https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/IND/ind_ppp_2020_UNadj_constrained.tif | 2020 dataset (retrieved 2026-10-31) | Cloud-accessible GeoTIFF read via HTTP byte-range window over Wayanad bbox and cached locally. | CC BY 4.0 |

## 4. Quality & ML Benchmarks (`M1`, `C3`)

| Component | Artifact / Dataset | URL or `PLACEHOLDER` | Date | What It Says (<=15-word quote or paraphrase) | Licence / Terms |
| --- | --- | --- | --- | --- | --- |
| `M1` USGS South Fork real aerial frames | `SEKI_SouthFork_AerialImages_F02-2.zip` | https://www.sciencebase.gov/catalog/item/67353631d34e6fbce7b5d58f | 2024 survey (retrieved 2026-10-31) | Post-debris-flow Ricoh GR II aerial imagery over South Fork Kings River, Sequoia National Park. | US Government Public Domain |
| `M1` OpenCV BRISQUE SVR model & range | `brisque_model_live.yml`, `brisque_range_live.yml` | https://raw.githubusercontent.com/opencv/opencv_contrib/4.x/modules/quality/samples/brisque_model_live.yml | Retrieved 2026-10-31 | Pre-trained LIVE IQA SVR weights distributed in `opencv_contrib/modules/quality/samples`. | Apache-2.0 |
| `C3` CRASAR road-damage assessment model card | `CRASAR-U-DROIDs-RDA_AAAI26_Simple_VanillaUNet` | https://huggingface.co/CRASAR/CRASAR-U-DROIDs-RDA_AAAI26_Simple_VanillaUNet | Retrieved 2026-10-31 | Model card metadata: `"license: mit"`, 4-channel `(RGB + road mask)` `MaskedUNet` road-damage segmenter. | MIT |
