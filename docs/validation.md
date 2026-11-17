# Validation

Every number here comes from a run in `data/runs/` (gitignored; run ids given) or from the USGS files listed in `data/LICENSES.md`. Nothing is estimated unless labelled.

## Datum (confirmed 31 Oct, 17:40 IST)
The USGS metadata (`SEKI_SouthFork_DebrisFlow_GNSS_metadata.xml`) states the RTK points are **NAD83(2011)** (EPSG:6319 / UTM 11N EPSG:6340), ellipsoid heights on GRS80, orthometric heights NAVD88 via GEOID18, with checkpoint accuracy ~0.03 m horizontal and ~0.07 m vertical (95%). Our map is placed by camera GPS (WGS84). PROJ gives the difference at South Fork for epoch 2024.33 as **1.52 m towards 279° (west) and −0.63 m in height** (ITRF2014 and ITRF2020 routes agree to 1 mm). `accuracy/datum.py` now converts the checkpoints into the map's frame before comparing. **This converts the reference, not the map:** checkpoints still only measure error. Results before the conversion are kept in each run as `accuracy.pre_datum.json` and quoted below in brackets.

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
| 2 (SF10, SF11) | 22.63 m | 25.65 m | **34.21 m** (35.01 m before datum conversion) | 34.43 m | targets found by `accuracy/find_targets.py`, confirmed visually (crops in the run's `targets/`) |

- Both shifts are **~35 m across the flight line, 3–5 m along it**: the signature of the roll ambiguity.
- Three more targets are visible (SF09, SF12, SF18/19 candidates) but their numbers can't be read at 5 cm, and their implied shifts don't fit; excluded rather than guessed.
- Datum converted (see top); it changes this result by under 1 m.
- ASPRS Ed. 2 asks for ≥ 30 checkpoints for full compliance; N = 2 is a diagnostic, not a compliance test.

### Vertical (DTM vs 823 RTK ground points, ellipsoid heights; computed before the datum conversion, which would add ~0.6 m)
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
| 3 (SF16, SF17, SF18) | 0.59 m | 6.07 m | **6.09 m** (6.42 m before datum conversion) | 7.65 m | detector candidates confirmed visually; IDs by consistent shift |

- All three shifts point the same way (~0.5 m east, 4–8 m north): a correctly shaped map placed by consumer-grade camera GPS. The datum conversion removed most of the east–west error (1.07 → 0.59 m) but almost none of the north error, so **the ~6 m north offset is the map, not the datum.** USGS states ~3 m horizontal for these camera positions.
- **Compared with Run 1 (single strip): 34.2 m → 6.1 m** from flight geometry alone. That's the capture-protocol rule in numbers.
- N = 3 is far below the ASPRS recommendation of 30; we report it as a prototype measurement, not a compliance test.

### Vertical
| Compared | N | Result |
|---|---|---|
| DSM at the 3 checkpoint targets (absolute) | 3 | RMSE_V **44.70 m** (44.08 m before datum conversion) |
| DTM vs RTK ground points, absolute (map shift applied) | 326 | mean offset **+43.49 m** (+42.86 m before) |
| same, after removing the constant offset (**relative heights**) | 326 | spread **1.09 m** (std; unchanged by the datum); 0.50 m if a slight tilt is also removed (before conversion) |

- **Absolute heights are unreliable** (+43 m): the model is placed vertically by the cameras' consumer-GPS altitudes, which read high (Run 1 found the same).
- **Relative heights are good to about ±1.1 m.** Debris volume, pile height, obstruction height and span banks are all measured against nearby ground, so the offset cancels. `accuracy/vertical.py` records this as `vertical_relative` in `accuracy.json`; `measure/` and `roads/` use it for height/volume tolerances (labelled), and the absolute RMSE_V stays reported as is.

### What the block shows about roads and landing zones (real outputs)
- **Trails under canopy:** 16 trail segments fall inside the map; their corridors are only 5–43% visible (tree canopy and green vegetation are set aside as "not visible"). With the assessment engine's 70% minimum, every one is **unknown**, not open or blocked. A drone cannot certify a forest trail it cannot see; the tool says so instead of guessing.
- **The ~6 m horizontal offset** (north, after datum conversion) also means OSM trail lines sample ground ~6 m from the real trail. Shifting the map by the checkpoint error would turn checkpoints into ground control, which the brief forbids; we report it instead.
- **Landing zones:** no candidate for either helicopter type (FATO 24 m / 38 m) met slope ≤ 7° (PLACEHOLDER) and the clear safety ring anywhere in this steep, forested canyon.

## Run 3: our own footage, DJI Neo 2 video (clip 0149, 20 Aug 2026)

**Data:** one consumer-drone video clip. `pipeline/video_frames.py` scored 880 frames for sharpness and kept the sharpest per 2 m of travel: **220 frames**, geotagged from GPS decoded out of the clip's own telemetry stream. No checkpoints exist for this site, so **no accuracy figure** is possible; the altitude reference of the telemetry is unknown, so heights are relative only.

| Tier | Run id | Time | Peak memory | Orthophoto extent | Reconstruction |
|---|---|---|---|---|---|
| quick | `2026-10-31_1111_neo2_0149_quick` | **67.7 min** (`total_seconds` 4059.5; monotonic, unaffected by the clock change) | 8.24 GiB | 4.32 ha at 5 cm (includes smeared area, see below) | 214 of 220 frames, in **7 separate pieces** (97, 64, 20, 16, 6, 6, 5 images), joined by GPS only |

Stage times: feature matching + reconstruction 46.6 min, meshing 19.0 min, everything else under 2.5 min.

**What came out** (preview: `data/screenshots/neo2/ortho_preview.png`):
- **The open sports ground is usable**: pitch, goals, people, tennis court and the path beside it are sharp and recognisable.
- **Everything around it is smeared**: tall buildings and trees are streaked outward. The quick tier drapes images over a smoothed ground surface, so tall objects seen at an angle smear across it; with the reconstruction in 7 GPS-joined pieces there is no single consistent model to fix that.
- The 4.32 ha extent therefore overstates the useful map; the usable part has not been measured.

**What this means for the product**
1. A casual video clip is not a survey: oblique views of tall objects and a path that doesn't revisit the same ground give weak, fragmented reconstructions. This is the same lesson as Run 1 from a different angle: **capture geometry decides the result**.
2. Capture guidance for responders: camera pointing straight down, steady height, overlapping parallel passes; open ground maps well, built-up areas need more height and overlap.
3. The video path works end to end (telemetry → geotagged frames → map in ~68 min on this laptop) and the tool shows its failure plainly instead of hiding it.

### Run 3 with the first-look tier (5 Nov)
| Tier | Run id | Time | Peak memory | Orthophoto | Frames placed |
|---|---|---|---|---|---|
| quick (above) | `2026-10-31_1111_neo2_0149_quick` | 67.7 min | 8.24 GiB | 4.32 ha at 5 cm | 214 of 220, in 7 pieces (largest 97) |
| first | `2026-11-05_0053_neo2_0149_first_first` | **26.7 min** | 11.0 GiB | 2.06 ha at 10 cm | 201 of 220, in **15 pieces** (largest 52) |

- The open playing field is recognisable in 27 minutes; buildings are smeared as in the quick tier.
- Fewer match pairs break the video into more, smaller pieces, joined by GPS only. Where pieces overlap, part of the field appears twice, offset (seen in the orthophoto). Peak memory was higher than the quick tier's, which we have not explained.
- No checkpoints, so no accuracy figure.

**What it means:** for a casual video clip the first look gives a picture of open ground in under half an hour, but it is more fragmented than the quick tier and can show the same ground twice. Use it only to see where open ground is, then wait for the quick map.

## Run 4: USGS South Fork, flight F02 part 2 (one long line), a search for more checkpoints (3 Nov)

**Why:** the block (Run 2) rests on 3 checkpoints; USGS surveyed 18 panel targets and 5 chalk marks. The other F01-4 candidates do not qualify (SF15, SF19, SF20 are chalk marks not identifiable at 5 cm; SF14 lies at the map edge with one weak candidate 27 m away), so we processed the one remaining flight we hold, `F02-2`.

**Data:** 61 images (Ricoh GR II), one line about 990 m long and about 100 m wide, flown from 1,466 m down to 1,242 m above sea level. Processed exactly like the others: quick tier, no ground control.

| Tier | Run id | Time | Peak memory | Orthophoto | Checkpoints confirmed |
|---|---|---|---|---|---|
| quick | `2026-11-03_0206_southfork_f02_2_quick` | **43.6 min** | 5.26 GiB | 4.85 ha at 5 cm, in **two disconnected patches** at the two ends of the line; nothing in the ~700 m between | **0** |

**What came out:** all 61 images were placed in one reconstruction, but the orthophoto exists only at the two ends. The north-west patch stops just short of target SF09, so that patch is displaced by tens of metres (not measured: no target inside it). The south-east patch contains only chalk marks SF21–SF23; the detector's candidates there are rocks and debris, not marks, so none was confirmed. **No new checkpoint, no accuracy figure for this run.**

**What it means:** a second, independent single-line flight fails the same way Run 1 did, which supports the rule from Run 1: never map from one straight line. The block figure stays **±6.1 m at 3 checkpoints**; with the public flights we hold, that is the limit, and it stays labelled as a prototype measurement (the standard asks for at least 30).

## Run 5: a "first look" tier on the same block (3 Nov)

**Why:** after a landslide a rough picture now beats a precise one later. We added a `first` tier to `pipeline/run_odm.py`: the same 248 F01-4 photos as Run 2, but features from downscaled images (`--feature-quality low`), fewer match pairs (`--matcher-neighbors 8`), 10 cm pixels and no report. Still no ground control.

| Tier | Run id | Time | Peak memory | Orthophoto | Checkpoints |
|---|---|---|---|---|---|
| first | `2026-11-03_2121_southfork_f01_4_first_first` | **50.3 min** (vs 145.6 min for the quick tier, 2.9× faster) | not recorded (see note) | 10.63 ha at 10 cm (vs 12.94 ha at 5 cm) | 2 (SF16, SF18) |

Stage times: feature matching and reconstruction 37.9 min (109.7 min in Run 2), texturing 4.3 min (27.9 min), orthophoto 3.5 min.

### Horizontal (orthophoto vs RTK targets, after the datum conversion)
| Checkpoints | RMSE_x | RMSE_y | RMSE_H | Max |
|---|---|---|---|---|
| 2 (SF16, SF18) | 8.19 m | 1.85 m | **8.40 m** | 10.30 m |

- Both points are clear panel targets in the crops. **Their shifts point in opposite east–west directions** (SF16 5.5 m west, SF18 10.2 m east), whereas in the quick tier all three agreed. So the first-look map is not only offset but slightly warped, and the two IDs could not be cross-checked by a consistent shift. SF17 shows no panel at this resolution.
- N = 2: indicative only.

**What it means:** the first look gives responders a picture of the whole block in under an hour, but positions are rougher and less consistent (±8.4 m at 2 points vs ±6.1 m at 3) and there is no height model. **Use it to see, not to measure;** measurements wait for the quick and full tiers.

**Note on the record:** the run finished normally, but its `run.json` failed the schema check (the new tier name was not yet in `contracts/run.schema.json`) before it was written, so the in-memory peak-memory samples were lost. Stage times and the total were rebuilt from the run's own `odm.log` timestamps. `run_odm.py` now writes the record before checking it.

### Run 5 repeated (4–5 Nov): same photos, same settings
| Run id | Time | Peak memory | Orthophoto | Checkpoints | RMSE_H | Max |
|---|---|---|---|---|---|---|
| `2026-11-05_0004_southfork_f01_4_first2_first` | **49.2 min** | **6.92 GiB** | 11.73 ha at 10 cm | 2 (SF16, SF18) | **11.41 m** | 13.91 m |

- Time is close to the first run (49.2 vs 50.3 min), and peak memory is now recorded: 6.92 GiB, the lowest of any block run.
- **The errors are not repeatable.** SF16 moved from (5.5 m W, 2.2 m N) to (5.7 m W, 5.8 m N); SF18 from (10.2 m E, 1.4 m N) to (1.8 m W, 13.8 m N). Same photos and settings gave a differently warped map, because the reconstruction's sampling choices differ between runs.
- Only one panel was found near SF17 and SF18; we assigned it to SF18 because its shift is northward like SF18 in every other run. SF17 was not found. N = 2: indicative only.

**What it means:** the first look takes about 50 minutes every time, but how far off it is changes from run to run (±8.4 m and ±11.4 m so far). This confirms the rule: **the first look is for seeing, never for measuring.**

## Run 6: a "middle" tier on the same block (4 Nov)

**Why:** the first look (Run 5) is fast but warped; the quick tier (Run 2) is accurate but takes 2 h 26 min. We tested a setting in between: the same 248 F01-4 photos, features from medium-size images (`--feature-quality medium`), each photo matched with its 12 nearest neighbours (`--matcher-neighbors 12`), full 5 cm pixels, no report. Still no ground control.

| Tier | Run id | Time | Peak memory | Orthophoto | Checkpoints | RMSE_H | Max |
|---|---|---|---|---|---|---|---|
| quick (Run 2) | `2026-10-31_0546_southfork_f01_4_quick` | 145.6 min | 8.61 GiB | 12.94 ha at 5 cm | 3 | 6.09 m | 7.65 m |
| **middle** | `2026-11-04_2243_southfork_f01_4_middle_middle` | **80.2 min** (1.8× faster) | 8.77 GiB | 13.14 ha at 5 cm | 3 | **6.06 m** | 7.72 m |
| first (Run 5) | `2026-11-03_2121_southfork_f01_4_first_first` | 50.3 min | not recorded | 10.63 ha at 10 cm | 2 | 8.40 m | 10.30 m |

Stage times: feature matching and reconstruction 57.7 min (109.7 min in Run 2), texturing 16.8 min (27.9 min), orthophoto 2.5 min (3.8 min).

- The same three panel targets (SF16, SF17, SF18) were found, and each one's shift agrees with its quick-run shift to within 0.4 m (all about 1 m west and 5–8 m north before the datum conversion). So the middle map is offset the same way as the quick map, not warped like the first look.
- After the datum conversion: SF16 dx 0.12 / dy 4.47 m, SF17 0.09 / 5.54 m, SF18 0.97 / 7.66 m. Almost all of the error is a north shift, as in Run 2.
- N = 3, as before: a prototype measurement (the standard asks for at least 30), and one block at one site.

**What it means:** on this block the middle tier gave the same horizontal accuracy as the quick tier in a little over half the time, at the same pixel size. **It is the better default for the first measurable map;** the first look stays for "see it in under an hour". Whether this holds on other terrain is untested (one block, 3 checkpoints). No height models were made in this run; heights still need the full tier.

## Tool vs tape (span, pile, staged block)
PENDING: needs our own field measurements; the survey flights were cancelled by rain (README disclosure).
