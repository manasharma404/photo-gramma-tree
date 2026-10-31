# Validation

Every number here comes from a run in `data/runs/` (gitignored; run ids given) or from the USGS files listed in `data/LICENSES.md`. Nothing is estimated unless labelled.

## Run 1: USGS South Fork, flight F01 part 5 only (single strip) — diagnostic

**Data:** 109 USGS images (`F01-5` zip; Ricoh GR II, global shutter, ~110 m AGL stated, 2.9 cm GSD stated), processed **without ground control** (GPS in the images only). Reference: USGS RTK targets and ground points (`SEKI_SouthFork_DebrisFlow_2024_RTK_GNSS.csv`).

**Why "diagnostic":** this zip is essentially **one straight flight line** over the debris flow (50 camera positions over the target area lie within 4.2 m of a 150 m line). With all camera positions on a line, GPS cannot fix the model's roll about that line. These results measure what that capture does, not our pipeline's best accuracy.

### Processing (this laptop: i5-13420H, 16 GB, RTX 4050; `data/machine.json`)
| Tier | Run id | Time | Peak memory | Map area | Notes |
|---|---|---|---|---|---|
| quick | `2026-10-31_0227_southfork_f01_5_quick` | 50.4 min | 6.97 GiB | 10.12 ha (orthophoto valid pixels) | from scratch; ~5.0 min/ha |
| full | `2026-10-31_0337_southfork_f01_5_full` | 66.6 min | 7.01 GiB | 9.07 ha | **incremental**: reused the quick tier's matching (`--rerun-from openmvs`); DSM/DTM at 0.10 m |

### Horizontal (orthophoto vs RTK targets)
| Checkpoints | RMSE_x | RMSE_y | RMSE_H | Max | Method |
|---|---|---|---|---|---|
| 2 (SF10, SF11) | 24.11 m | 25.39 m | **35.01 m** | 35.09 m | targets found by `accuracy/find_targets.py`, confirmed visually (crops in the run's `targets/`) |

- Both shifts are **34.7–34.8 m across the flight line, 3–5 m along it**: the signature of the roll ambiguity.
- Three more targets are visible (SF09, SF12, SF18/19 candidates) but their numbers can't be read at 5 cm, and their implied shifts don't fit; excluded rather than guessed.
- RTK horizontal datum: not stated in the CSV (likely NAD83(2011); ~1–1.5 m from WGS84 here). Negligible at this error; must be confirmed for a good run.
- ASPRS Ed. 2 asks for ≥ 30 checkpoints for full compliance; N = 2 is a diagnostic, not a compliance test.

### Vertical (DTM vs 823 RTK ground points, ellipsoid heights)
| Compared at | N | Mean dz | Std | RMSE | Tilt across track |
|---|---|---|---|---|---|
| surveyed positions | 823 | +58.6 m | 7.6 m | 59.1 m | −0.148 m/m (−8.4°) |
| surveyed positions + measured horizontal shift | 827 | +68.5 m | 10.7 m | 69.3 m | −0.231 m/m (−13.0°) |

- The model's shape is plausible: ODM's self-calibrated focal length matches the camera (0.7796 vs 0.7778 normalised) and it places the cameras 122.5 m above the reconstructed ground (USGS states ~110 m AGL).
- **The images' GPS altitudes sit 146 m (median; 132–169 m) above the surveyed ground**, ~36 m more than the stated flying height and beyond USGS's stated ~10 m vertical accuracy. ODM places the model vertically from those altitudes, so the ground comes out too high; the roll adds a cross-track tilt. We have not split the offset exactly between the two causes.

### What this means for the product
1. **Capture protocol rule: never map from a single straight line. Fly at least two parallel lines (or a cross).** One line gave a 35 m sideways error and a tilted height model even with a survey-grade camera.
2. Absolute heights from consumer GPS altitude can be off by tens of metres. Report heights **relative to the surrounding ground** (pile height, bank height), where a constant offset cancels, and say so in the UI.
3. Next run: add a neighbouring strip (`F01-4`) and repeat both tables.

## Run 2: USGS South Fork, flight F01 part 4 (a block of 5 parallel lines)

**Data:** 248 USGS images (`F01-4` zip), same camera, again **without ground control**. The parallel lines remove the single-strip roll ambiguity.

| Tier | Run id | Time | Peak memory | Map area | Notes |
|---|---|---|---|---|---|
| quick | `2026-10-31_0546_southfork_f01_4_quick` | 145.6 min | 8.61 GiB | 12.94 ha | from scratch, GPU features (`--feature-type sift`); ~11.2 min/ha |
| full | `2026-10-31_0819_southfork_f01_4_full` | 171.4 min (incremental) | 11.0 GiB | 13.19 ha | reused matching; DSM/DTM at 0.10 m; peak memory close to the 12 GB WSL limit |

### Horizontal (orthophoto vs RTK targets)
| Checkpoints | RMSE_x | RMSE_y | RMSE_H | Max | Method |
|---|---|---|---|---|---|
| 3 (SF16, SF17, SF18) | 1.07 m | 6.33 m | **6.42 m** | 7.88 m | detector candidates confirmed visually; IDs by consistent shift |

- All three shifts point the same way (~1 m west, 5–8 m north): a correctly shaped map placed by consumer-grade camera GPS. USGS states ~3 m horizontal for these camera positions; the remainder may include the RTK file's datum (likely NAD83(2011), ~1–1.5 m from WGS84 here; unconfirmed).
- **Compared with Run 1 (single strip): 35.0 m → 6.4 m** from flight geometry alone. That's the capture-protocol rule in numbers.
- N = 3 is far below the ASPRS recommendation of 30; we report it as a prototype measurement, not a compliance test.

### Vertical
| Compared | N | Result |
|---|---|---|
| DSM at the 3 checkpoint targets (absolute) | 3 | RMSE_V **44.08 m** |
| DTM vs RTK ground points, absolute (map shift applied) | 326 | mean offset **+42.86 m** |
| same, after removing the constant offset (**relative heights**) | 326 | spread **1.09 m** (std); 0.50 m if a slight tilt is also removed |

- **Absolute heights are unreliable** (+43 m): the model is placed vertically by the cameras' consumer-GPS altitudes, which read high (Run 1 found the same).
- **Relative heights are good to about ±1.1 m.** Debris volume, pile height, obstruction height and span banks are all measured against nearby ground, so the offset cancels. `accuracy/vertical.py` records this as `vertical_relative` in `accuracy.json`; `measure/` and `roads/` use it for height/volume tolerances (labelled), and the absolute RMSE_V stays reported as is.

### What the block shows about roads and landing zones (real outputs)
- **Trails under canopy:** 16 trail segments fall inside the map; their corridors are only 5–43% visible (tree canopy and green vegetation are set aside as "not visible"). With the assessment engine's 70% minimum, every one is **unknown**, not open or blocked. A drone cannot certify a forest trail it cannot see; the tool says so instead of guessing.
- **The ~6 m horizontal offset** also means OSM trail lines sample ground ~6 m from the real trail. Shifting the map by the checkpoint error would turn checkpoints into ground control, which the brief forbids; we report it instead.
- **Landing zones:** no candidate for either helicopter type (FATO 24 m / 38 m) met slope ≤ 7° (PLACEHOLDER) and the clear safety ring anywhere in this steep, forested canyon.

## Tool vs tape (span, pile, staged block)
PENDING: needs our own field measurements; the survey flights were cancelled by rain (README disclosure).
