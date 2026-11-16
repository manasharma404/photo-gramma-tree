# PLAN.md: Project Typhon, team Vortex (hackFront T8.2 "The First Map After The Landslide")

**Status: APPROVED by the lead, 31 Oct 00:30 IST.** Single source of truth for owners, timeline, bugs and decisions. Brief: `CLAUDE.md` (Update 2 overrides Update 1 overrides the rest).

## Finale plan (21–22 Nov, IIIT Delhi). DRAFT, 16 Nov: the lead approves or edits

Everything below this section is the round 1 record. This section is the plan for the finale.

### Core journey (one line)
A responder flies a consumer drone over a landslide. A rough map grows on the laptop while the drone is still flying; Typhon then says where each vehicle can go, which blockage to clear first, and **where to fly next**. One laptop, no internet.

**It is one loop, not a list of features:** see (the growing map) → suspect (debris found by the model and by the change in the ground) → decide (the road graph answers "clear first" and "fly next") → fly again. Every finale feature is one step of that loop.

### Why this plan (audit of 16 Nov)
| Flaw | What fixes it |
|---|---|
| The drone → map → road status chain has never given a real answer: all 498 South Fork segments read "unknown" | F2 and F3 below |
| "Immediate" is not true: the fastest usable map takes 50–80 min | F1 |
| No intelligence of our own: the road model is borrowed and writes empty scores without its weights; priorities are hand-set weights | F3, F4 |
| No before and after; debris outlines are drawn by hand | F2 |
| The output is a five-tab dashboard, not an answer | F4, F5 |
| Effort went to the edges (`export/` about 2,000 lines, `roads/` 296) | Cut list |

### Checked on 16 Nov
| Question | Finding | How checked |
|---|---|---|
| Do our photos record camera direction (needed to place a photo on the ground at once)? | **No.** USGS photos (Ricoh GR II) carry GPS, altitude and field of view only. Our Neo 2 telemetry decodes to position, altitude and ISO only | `exiftool` on a block image; `pipeline/dji_telemetry.py` FIELDS |
| So how does F1 work? | **Not by placing photos one by one: tested 16 Nov and failed** (photo centres a median 43.5 m off; the camera tilts forward and the ground is a steep slope). Second test, the mapping engine on every fourth photo: **11.6 min, right place (3.05 m median from our measured map), but only 2.58 of 13.14 ha, with holes.** **Third test, all photos solved together as they arrive: works.** 1.02 s per photo on a flight that takes one photo a second, so the map keeps pace with the flight; a typical point is a median 11.8 m from our measured map, and 9.8 / 14.3 / 17.6 m off at the three surveyed checkpoints. **F1 stays, reworded: the map grows while the drone flies** (not "in one minute") | `docs/validation.md`, Test 7 |
| Is there detailed terrain from before the slide at South Fork? | **Yes, 1 m:** `USGS 1 Meter 11 x34y403 CA_SierraNevada_B22`, 310 MB, **downloaded 16 Nov**. Lidar flown 3 Nov 2021 to 23 Sep 2022; the debris flow was on 9 Jan 2023, so it is from before the slide. It covers our whole map with no gaps | Tile metadata file; USGS data release text; read with rasterio |
| Is there drone landslide training data? | **Yes:** CAS Landslide Dataset (Xu et al., Scientific Data 2024), 20,865 images from satellites and drones, 9.2 GB on Zenodo, CC BY-NC 4.0, with different terms on some subsets (check each one used) | Zenodo record 10294997 and the paper |
| Is CRASAR-U-DROIDs worth downloading? | **No.** CC BY 4.0, but 219 GB and no landslides (hurricanes, tornado, eruption, wildfire, collapse). Keep its published road model as the comparison only | Hugging Face dataset page |

### Before the finale (groundwork: data, models, design, knowledge)
| When | Task | Owner | Done when |
|---|---|---|---|
| Tue 17 | Ask the organisers in writing: is the push before 2 pm Saturday the baseline, and may we bring trained weights, datasets and design specs? | Lead | Reply saved in this file |
| ~~Tue 17~~ done 16 Nov | F1 tests, three methods | Claude | Done: all in `docs/validation.md`, Test 7. Verdict: **go for "the map grows while the drone flies"** (method 7c); no-go for "a map in one minute" |
| ~~Tue 17~~ done 16 Nov | F1 on our Neo 2 night video | Claude | Done: **fails** (Test 7d). The camera looked across the field, not down; frames cannot be laid flat |
| Tue 17 – Thu 19 | **F1 test flight of our own:** daylight, camera pointing straight down, at least three overlapping parallel lines over open ground with a few things we can measure on the ground. Then run method 7c on it | Lead flies, Claude processes | Works / fails with numbers in `docs/validation.md`. **This decides whether a campus flight is in the demo** |
| Tue 17 – Wed 18 | F1, still open: how photos reach the laptop during a flight (or straight after landing) | Claude + lead | Written up as what we will actually do on the day |
| ~~Tue 17~~ done 16 Nov | Download the 1 m pre-event terrain and confirm its flight date | Claude | Done: file in `data/prefetch/usgs_1m/`, date and licence in `data/LICENSES.md` |
| Tue 17 – Thu 19 | One model, one job: find debris on roads in drone maps. Train on the CAS drone subsets; hold out one whole region for testing | Teammate | Weights file, and a score on the held-out region written to `docs/validation.md` (PENDING until run) |
| Wed 18 | Hand-label about 50 South Fork road crops (debris / clear) as our own test set | Lead + teammate | Labels in `data/eval/`; the model's score on them recorded |
| Wed 18 | Wayanad pack: OpenStreetMap roads and the Copernicus terrain model, tiles built for offline use | Claude | Opens with Wi-Fi off |
| Wed 18 – Fri 20 | Home page 3D object and the design spec | Lead | Spec file in `docs/`; model file ready to load |
| Thu 19 | Our own survey flight with checkpoints, weather allowing; process it overnight | Lead | Run logged in `data/runs/` |
| Thu 19 | Show the app to one working responder (NDRF, SDRF or fire service) and ask what they'd need in the first hour | Lead | Their words, with permission, in `docs/`; nothing invented if nobody answers |
| Fri 20 | Runbook, pitch rehearsal, hotspot and phone check, laptop prepared; baseline pushed and checked from a fresh clone | All | Fresh clone builds and passes its tests |

### The 22 hours (Sat 14:00 → Sun 12:00), built fresh
| # | Feature | Owner | Window | Done when |
|---|---|---|---|---|
| — | Set up, check the baseline, collect the Neo4j AuraDB access at the partner desk (from 14:30) | All | 14:00–15:00 | App runs; advisor reads from AuraDB |
| — | Campus flight, if the organisers allow it and the test flight worked | Lead | 15:00–16:30, daylight | Photos on the laptop |
| F1 | **The map grows while the drone flies:** each photo lands on the map about a second after it arrives; labelled "rough, about 10 to 20 m, not for measuring"; the measured map replaces it when ready | Lead + Claude | 15:00–20:00 | Runs on a photo set chosen on the day, replayed at flight speed; seconds per photo shown on screen |
| F3 | **Debris on roads:** the trained model scores every road segment; fused with the height check; statuses stop being "unknown" where there is evidence | Teammate | 15:00–23:00 | South Fork shows real statuses, each with its evidence crop |
| F2 | **The slide finds itself:** our height model minus the pre-event terrain, matched on stable ground, gives deposit and scar areas and a volume with a tolerance | Lead + Claude | 20:00–01:00 | Deposit outline and volume appear with no drawing |
| — | **Mentor Round 1 (40 marks)** at our table. The F1 skeleton is already on screen | All | 20:00–21:00 | Round 1 sheet handed over; three promises stated |
| F4 | **The answer and the plan in Neo4j (the headline):** per vehicle, the route or "cut off"; **clear first** (which single blockage reconnects the most people); **fly next** (which unchecked road, once surveyed, settles the route for the most people), drawn as a flight path | Teammate, then lead + Claude on the map | 23:00–04:00 | One sentence per settlement; both answers computed in Neo4j, NetworkX as the fallback |
| F5 | **Judges break it:** tap a road to block it or pick a vehicle; the plan and the next flight redraw in seconds | Lead + Claude | 01:00–04:00 | Works on the phone and the laptop |
| F6 | Home page 3D object and the design pass from the spec | Lead | in gaps | Matches the spec |
| — | Join everything, run every demo action end to end, failure cases, sleep in turns | All | 04:00–07:00 | Runbook passes twice |
| — | Progress update on Discord (required by 07:30) | Pitch owner | 07:00–07:30 | Posted |
| — | **Our code freeze 08:00** (the guide says no new features after 09:00). Demo video and deck finished **before 10:00**, because Round 2 and the track reviews fill 10:00–11:45 | All | 08:00–09:45 | Video and deck files ready; backup video of the demo saved |
| — | **Mentor Round 2 (60 marks)** and the Neo4j track review, product running live at the table | All | 10:00–11:45 | — |
| — | **Submit by 11:30** (the portal locks at 12:00 sharp); last push from the phone hotspot if the venue Wi-Fi is slow | Pitch owner | 11:00–11:30 | Repo link, video and deck submitted |
| — | If we are in the Top 12: stage tech check at 12:15, six minutes on stage from 12:30 | All | 12:15 onwards | — |

**If we slip:** F5 shrinks to "pick a vehicle" only; F2 falls back to South Fork only; F6 keeps the round 1 home page. F1, F3 and F4 are the product and are not cut. A fix that lands after 08:00 does not ship.

### Cut list (no more work before or during the finale)
Exports (PDF, KMZ, COG), the situation report, new processing tiers, the guided tour, more datasets (SpaceNet 8, FloodNet), more scenarios (Sikkim, Himachal). They stay in the repo and go on the roadmap slide. Nepal's 26 August 2026 flash flood is the case study for the pitch and the video (lead's decision, 17 Nov; it replaces Kedarnath) and joins as a scenario built from cited reports (teammate brief, T4).

### Rules that stay
Numbers on screen and on slides come from runs we can show. Hand-set weights are not called AI. The rough map is labelled rough. The model's score is the one measured on images it never saw.

### How we are scored, and how we play each round (from the Participant Guide)
100 teams. Only the two mentor rounds decide the Top 12; only the Top 12 meet the jury.

| Round | Marks | What carries the most | How we play it |
|---|---|---|---|
| **Mentor Round 1**, Sat 20:00, at the table | 40 | Problem understanding 10; originality and edge 10; architecture 8; fit to the problem statement 6; plan for the night 6 | One printed page: the root cause in one sentence, what exists and why ours is better, the loop as a diagram, and **three promises for the night: F1, F3, F4**. Round 2 marks us against these promises, so we promise only what our tests already support. Show the growing map already running |
| **Mentor Round 2**, Sun 10:00, at the table | 60 | Working product live 16; technical depth 14; progress since Round 1 10; reliability on the mentor's input 10; pitch and questions 10 | Product already running at 09:55, with a "reset demo" action. Open with the three promises and tick them against the commit list. Hand the mentor the input menu below. A recording or mock-up scores nothing here |
| **Jury**, Top 12, six minutes on stage including the demo | 100 | Innovation 30 (the idea is ours **and runs live**); technical depth and finale build 25; live demo 14 plus reliability on the jury's input 11; problem 15; pitch and path 10 | Start the growing map in the first ten seconds so it fills in while we talk. Timing: problem and user 0:40; the loop live 3:00; a judge taps a road 0:50; what is underneath and what we built in 22 hours 0:45; first adopter, payer, next milestone 0:45 |

**The input menu (so "your own input" costs a judge five seconds):** pick one of three photo sets (the South Fork block; a single straight line, which Typhon warns about, our 34 m lesson; our own flight); tap any road to block it; pick a vehicle; send a field report from their own phone with the PIN.

**Failure cases we rehearse:** Wi-Fi off (still works); Neo4j stopped (falls back, and says so on screen); photos with no GPS or too blurred (refused with the reason); a wrong PIN; a road tapped where nothing is known (stays "unknown", and becomes a "fly next" candidate).

**Habits that score:**
- One person owns the demo and the pitch from 14:00 and writes no feature code after 04:00.
- Commit small and often with clear messages; the commit list is the evidence for 10 + 7 marks. Tag the starting point before 14:00 on Saturday.
- Every member can explain every layer: the guide says judges will question the architecture and the code, and it allows AI tools only on that condition.
- Sleep in turns.
- Know the one-minute story by heart: who the user is, who pays, what we built, what it does. **Who pays is still our assumption** until a responder or official confirms it.

**Tracks:** the Neo4j track (INR 25,000 plus credits) is reviewed separately on Sunday 10:00–11:45 and needs Neo4j in the working build: F4 is that. The Women Track is also reviewed then; if the team is eligible, ask the organisers how to be considered. The Sarvam (Indian-language AI) track would mean a spoken briefing or voice reports, but it needs the internet, which works against "one laptop, no internet": **not planned**, unless the lead wants it as a clearly labelled online extra.

### Innovation sweep (16 Nov): what is ours, in order of strength
| # | Idea | Why it is new and grounded | State |
|---|---|---|---|
| 1 | **Fly next** | Mapping tools wait for the pilot to finish. In the first hours the scarce thing is battery, so the question is which road to look at next. Ranked by how many people's routes depend on each unchecked road | Not built; queries to be tested by the teammate (T3) |
| 2 | **The map grows while the drone flies** | A rough map during the flight, replaced by the measured one | Works on survey photos looking straight down (Test 7c); **fails on our oblique night video (7d); needs our own test flight** |
| 3 | **The slide finds itself** | Our height model minus the terrain from before the event; no hand drawing | Pre-event terrain in hand for South Fork; not built. For an Indian site only the 30 m Copernicus model exists, which is far coarser: say so |
| 4 | **Every answer carries how far it can be trusted** | The rough map (10 to 20 m) may only raise a suspicion and a "fly next"; only the measured map (±6 m at 3 checkpoints) may set a road to blocked | A rule to build into F3/F4; it is what makes the loop honest |
| 5 | **Clear first** | One blockage whose removal reconnects the most people, from the graph | Not built; teammate T3 |

Anything outside these five is polish. If time runs short, polish goes first.

### The pitch deck
**Is one required? Yes.** The final submission is the repository link, a demo video and a pitch deck, before 12:00 on Sunday. The guide does not name a file format; the steps come on Discord before the finale. We export a PDF and keep the editable deck, so either can be submitted.

- **Two uses, one file:** on stage there is time for three or four slides around the live demo; the submitted file is read without us, so it carries the evidence.
- **At most eight slides:**
  1. The one-line journey and the loop diagram.
  2. The root cause: responders lack knowing which roads to trust and where to look next, with one cited fact.
  3. What exists and where it stops, against ours.
  4. "Live demo" (a title only; we switch to the app).
  5. What is underneath: the layers, and where Neo4j sits in the code.
  6. Evidence: each number with how many points it rests on and which run it came from.
  7. Built in the 22 hours: the starting point against the end, with the commit list.
  8. The path: first adopter, payer, deployment, next milestone, and the limits.
- **Rules:** maximum contrast, nothing under about 30 px, one idea per slide, the honest details in the speaker notes, anything unmeasured shown as PENDING.
- **Prepare before the finale:** the skeleton with PENDING slots. **Fill at the finale:** numbers, screenshots, the commit list. It must be finished before 10:00 on Sunday.
- **Demo video:** the updated product, with the team briefly on camera and a teammate's own voice; recorded 08:00–09:30 on Sunday from the frozen build. Keep a second, shorter copy as the stage backup.

## Facts checked on 31 Oct, 00:15 IST
| Item | Value | How checked |
|---|---|---|
| CPU | Intel Core i5-13420H | `Win32_Processor` |
| RAM | 15.7 GB visible to Windows (16 GB installed) | `Win32_ComputerSystem` |
| GPU | RTX 4050 Laptop, 6 GB, driver 592.82 | `nvidia-smi` |
| **Free disk** | 17 GB on C: (only drive) at first; **47.3 GB after the Docker cleanup (D1)**. The brief assumed ~119 GB | `Get-PSDrive` |
| Docker | Installed, **engine not running** | `docker version` |
| `.wslconfig` | Does not exist yet | `Test-Path` |
| ffmpeg/ffprobe | 9.0.2 installed | `Get-Command` |
| exiftool | **Not installed** | `Get-Command` |
| Neo 2 clip 0148 | 4K HEVC, 59.94 fps, 56.1 s, 56.6 Mb/s, 379 MB, created 20 Aug 17:39 UTC (23:09 IST) | `ffprobe` |
| Neo 2 clip 0149 | 4K HEVC, 59.94 fps, 177.1 s, 56.5 Mb/s, 1.25 GB, created 20 Aug 17:40 UTC (23:10 IST) | `ffprobe` |
| Telemetry | Both files carry a DJI `dvtm_NEO2.proto` data stream ("CAM meta"). **GPS in every frame** (decoded by `pipeline/dji_telemetry.py`; exiftool 13.59 cannot read it). See step 4 in the decisions log | `pipeline.video_check` |
| Stabilisation | `EIS:RS` (electronic stabilisation, rolling shutter) | MP4 comment tag |
| Content | Night, floodlit grass football ground, players moving, mostly oblique view, buildings behind | 5 sampled frames, viewed |

**What the footage means:** it is lit well enough to see, but plain grass, moving people, an angled camera and stabilisation warping (EIS) all work against mapping. Expect a weak or failed reconstruction. That's fine: the brief says to keep it as "what responders have today" and report the failure with numbers. **South Fork (USGS) carries our accuracy and measurement claims.**

## Owners
| Area | Folders | Owner |
|---|---|---|
| Map, measurements, everything on screen | `pipeline/ accuracy/ measure/ roads/`, all of `web/` (map, 3D, panels, styling) | Lead + Claude |
| Decisions, field delivery, exports | `advisor/ quality/ ml/ api/ neo4j/ export/`, `scripts/qr.py`, `config/vehicles.yaml`, `config/priority.yaml` | Teammate (see `TEAMMATE.md` v3, prompts `docs/teammate_prompt.md`, `docs/teammate_followup_1.md`) |
| Shared, frozen once approved | `contracts/`, this file | Lead decides |

## Work plan (lead + Claude), one feature at a time
| # | Step | Done when | Target (IST) |
|---|---|---|---|
| 1 | Machine check → `data/machine.json`; start Docker; GPU check; **pull one ODM image** (GPU first, CPU only if GPU fails, to save disk) | JSON shown; `nvidia-smi` runs inside the container; image tag pinned here | 01:00 |
| 2 | Skeleton: `git init` on `main`, `.gitignore`, `README`, `docs/AI_DISCLOSURE.md`, `data/LICENSES.md`; Python venv + `requirements.lock` | Tree shown | 01:30 |
| 3 | Contracts: schemas + mock examples (incl. the 3 new ones below) + a test that validates them | Test passes | 02:00 |
| 4 | Neo 2 check → `data/raw/neo2/video_report.json`: ffprobe, telemetry decode (GPS yes/no), brightness and sharpness on ~20 frames | Report shown | 02:30 |
| 5 | USGS South Fork: RTK CSV + **smallest** image zip; EXIF GPS of every image; plot centres vs tarps; `subset.txt` (~150 images); licence logged; datum read from CSV | Plot + subset shown | 04:00 |
| 6 | Quick tier on the subset → `run.json` (stage times, peak memory, area, GSD) | Orthophoto opens with rasterio | 06:00 |
| 7 | Accuracy: find tarps in orthophoto (template match, else manual click), datum conversion, errors → `accuracy.json` with N | Numbers from a run, N stated | 09:00 |
| 8 | Full tier → DSM/DTM; heights vs RTK topography (absolute + relative) → `docs/validation.md` | Table filled from runs | 12:00 |
| 9 | Neo 2 video tier (frame selection uses our sharpness check now, teammate's ML scores later); report result or failure with numbers | Result or failure written up | 13:00 |
| 10 | Measure: volume over a deposit, landing zones, span (if a channel exists), working space, as `measure.router`; `accuracy.router` for `/spec`. **`roads/`**: OSM ways clipped to the map, ≤ 50 m segments, DSM cross-sections → `segments.geojson` + `places.geojson` (incl. landing zones); write it during ODM waits, test on a synthetic DSM, hand to the teammate ~15:00 | Endpoints return `measurement.json`; both GeoJSONs validate | 15:00 |
| 11 | Web: MapLibre 2D map, three.js terrain from DSM + orthophoto, **data panels** (road status per vehicle from `GET /advisor/state`, priorities, measurements, accuracy, field reports), spec card; styling. Built against contract mocks first. **Her** `api/` app serves it and mounts our routers | Runs offline, screenshot | 18:00 |
| 12 | Exports: COG, KMZ, GPKG, GeoJSON, PDF; each opened in its target app | Opened in QGIS / Google Earth | 19:00 |
| 13 | README (what's real / public / estimated, how to run), offline check (Wi-Fi off, phone on hotspot) | README complete; phone opens the map | 20:30 |
| 14 | **Round 1 submission: a PPT + the GitHub link** (no live demo, no rehearsal). Slides use only numbers from runs; placeholders listed, not invented | PPT ready, repo link works from a fresh clone | 23:00 |
| — | **Code freeze 21:30**, submit by 23:00 | | |

**If we slip:** steps 9 and 12's PDF are the first to shrink; Medina River change detection is already skipped unless time appears (say so in the README).

## New contracts to freeze with the teammate (proposed)
1. **`image_quality.json`** (teammate's ML → `pipeline/`): see `contracts/image_quality.schema.json`: `{mock, method: "ml_model"|"standard_check", model, version, source, items: [{image: "<file or video:frame_index>", score: 0-1, usable, reasons: [...]}]}`. The pipeline uses it to drop frames before ODM. Until it arrives, `pipeline/` uses our own brightness + Laplacian sharpness check, labelled **"standard sharpness check"**, never "AI".
2. **Advisor router:** her module exposes `advisor.router` (a FastAPI `APIRouter`) and a static folder for the phone page. We mount it at `/advisor` and serve the page at `/field`.
3. **`GET /advisor/state`:** `{"mock": bool, "segments": [{"segment_id", "status_by_mode": {"truck","jeep","foot"}, "source": "geometry|field_report|scenario"}], "updated_at"}`. `web/` colours roads only from this.
4. Existing contracts from the brief stay as written: `segments.geojson`, `places.geojson`, `ml_scores.json`, `access_report.json`.

## Decisions needed from the lead
| # | Question | My recommendation |
|---|---|---|
| D1 | **Disk: 17 GB free, brief wants ≥30 GB free during ODM runs.** | Pull only the GPU ODM image; download one USGS zip at a time and delete it after extracting; move (not copy) the two videos into `data/raw/neo2/`; and if you can, free ~15 GB yourself (I won't delete anything of yours). |
| D2 | Install exiftool? | Yes (winget, ~10 MB). Needed for the GPS check the brief asks for; I'll also try decoding the DJI telemetry stream directly. |
| D3 | `.wslconfig`: `memory=12GB, swap=16GB, processors=10` per Update 2. Swap also lives on C:. | Use `swap=8GB` instead, because of D1. Needs a WSL restart. |
| D4 | Folder location: `Desktop\hackfront\vortex`, git on `main`, no GitHub remote yet. | Keep it there; add the remote when you give me the URL. |

## Decisions log
| When | Decision | By |
|---|---|---|
| 31 Oct 00:15 | Project folder `vortex` created at `Desktop\hackfront\vortex` with the Update 2 layout | Claude (default; lead to confirm) |
| 31 Oct 00:30 | PLAN.md and TEAMMATE.md approved; D2–D4 approved as recommended | Lead |
| 31 Oct 00:30 | D1 (disk): lead frees space by cleaning RAKSHAM's Docker data (project `farq`). Docker's disk file is 47.4 GB: 18.3 GB build cache, 9.4 GB images, 3.8 GB volumes, ~16 GB already-deleted space not yet returned to Windows. Plan: stop farq, turn off its auto-restart, prune build cache, trim and compact the disk file. Images and volumes (RAKSHAM's data) are kept | Lead runs it; Claude verifies sizes after |
| 31 Oct 00:50 | D1 result, measured: Docker disk file 47.4 → 15.7 GB; C: free 17 → 47.3 GB. RAKSHAM images and volumes kept; its containers no longer auto-start | Claude measured |
| 31 Oct 01:00 | Step 1 done. ODM pinned: `opendronemap/odm:gpu@sha256:c6ecdec7764094732248517c51d6430fbc9dad61b586daafded04745026d9ed8` (9.38 GB, built ~2 months ago). `nvidia-smi` inside it sees the RTX 4050 (6 GB). CPU image not pulled. Docker sees 12 GB RAM, 10 CPUs. C: free after the pull: 31.3 GB | Claude measured |
| 31 Oct 01:20 | Step 2: git on `main`; Python env via `uv` (Python 3.12.15, since uv could not install 3.11; brief says 3.11+); `uv.lock` + `requirements.lock`. Lead offered to move data to an external drive if disk-saving gets in the way | Claude |
| 31 Oct 01:25 | Step 3: 10 contracts in `contracts/` (schema + mock example each), `tests/test_contracts.py` 24/24 pass. **Changes from the brief's section 6:** `run.tier` adds `video`, optional `inputs.quality_filter`; `accuracy.used_gcps` is fixed to `false`, `found_by` adds `template` (USGS tarps), optional `datum_note`; `ml_scores.json` is wrapped as `{mock, scores: [...]}` so it can carry `mock`; `measurement.tolerance.unit` adds `m2`, `deg`; `image_quality.json` puts `method` (`ml_model` / `standard_check`), `model`, `version` at the top instead of per item; new `places.geojson` (adds `kind`, `source`, `nearest_segment_id`) and `advisor_state` schemas | Claude; lead to confirm |
| 31 Oct 02:00 | Lead: teammate prompt waits until she finalises her scope; focus on the lead's work | Lead |
| 31 Oct 02:00 | Step 5 blocked: ScienceBase (and its S3 / CMGDS mirrors) refuse scripts behind a Cloudflare bot check; the lead downloads the RTK CSV and smallest image zip by hand | Lead |
| 31 Oct 02:10 | **Work division (TEAMMATE.md v3):** her six docs are hers except R1 (accuracy validator, lead). Moved to her: `roads/` (segment measurements), `api/` app shell + offline serving + QR + hotspot, `web/src/panels/`, status per vehicle with reasons, quality checks. Lead keeps ODM pipeline, accuracy, `measure/` (span, volume, landing zones, working space), exports, map + 3D + all styling | Lead (rule), Claude (details) |
| 31 Oct 02:10 | **Contract changes:** modes are `fire_truck, ambulance, jeep, foot` (was truck/jeep/foot; N1 picked by Claude under the lead's "decide this") in `segments`, `advisor_state`, `access_report`; `segments.status_by_mode` and `decision` optional (status comes from `/advisor/state`); `advisor_state` adds `reasons_by_mode`, `needs_verification`; `access_report.reopen_plan` adds `mode`, `reasons`; new `priorities.json` (`decision_support: true` enforced); `image_quality.json` optional `coverage` block. 32 tests pass | Claude |
| 31 Oct 02:30 | Repo pushed to GitHub `manasharma404/photo-gramma-tree` (`main`), merged with GitHub's starter commit; fresh clone installs and passes 32 tests. At the lead's request, Claude co-author lines were removed from all commits and force-pushed (explicit go; teammate had not cloned) | Lead |
| 31 Oct 02:45 | **Step 5 (USGS) findings.** Lead downloaded `F01-5` (109 images) and `F02-2` (61) + RTK CSV. Image EXIF: WGS84 (G1150), ellipsoid heights; USGS states ~3 m horizontal, ~10 m vertical. **RTK CSV datum not stated** in the file; its metadata page is not on the CMGDS mirror (404). Likely NAD83(2011) + NAVD88 (orthometric − ellipsoid ≈ 28.3 m in the file) → must confirm before step 7; NAD83 vs WGS84 is ~1–1.5 m here. **The zips are flight-line fragments:** `F01-5` is one strip along the flow over targets SF08–SF13 (7 of 23 targets under any image, 6 seen by ≥3); `F02-2` is separate short passes. Subset = all 109 `F01-5` images (`subset.txt`, `subset.json`, `subset.png`). A single strip has no side overlap: expect weaker geometry; a neighbouring strip (likely `F01-4`) would make a proper block | Claude measured |
| 31 Oct 03:20 | **Step 6 done: first quick tier**, run `2026-10-31_0227_southfork_f01_5_quick`. 109/109 images reconstructed in 1 component (130,280 sparse points). **50.4 min total** (opensfm 34.1 min, texturing 11.2, orthophoto 2.4), **peak memory 6.97 GiB** (docker stats, 2 s samples), **orthophoto valid area 10.12 ha**, pixel size 5.0 cm (set by `--orthophoto-resolution 5`; capture GSD stated by USGS is 2.9 cm), EPSG:32611 → about 5.0 min/ha for this tier on this laptop. ODM's own report gives 15.3 m average "GPS error" (camera GPS vs reconstruction, internal, not our checkpoint accuracy). The orthophoto has two pieces with a gap between them (no images there); targets SF10, SF11, SF19–SF23 fall inside. **GPU was probably not used for features** (no GPU line in the log; ODM's default feature type is likely CPU-only) → test `--feature-type sift` next run. **Disk:** C: free 36.4 → 21.2 GB; project folder 5.2 GB, Docker's disk file grew 15.7 → 26.0 GB (space inside it is reused by later runs, but not returned to Windows) | Claude measured |
| 31 Oct 04:10 | **Step 7, first accuracy result (single-strip diagnostic).** Targets are ~0.5–0.8 m white squares with bluish "bowtie" triangles (some black/white checker); `accuracy/find_targets.py` finds them by white + bluish pixels; IDs assigned by consistent shift and confirmed visually (crops in `data/runs/2026-10-31_0227_.../targets/`; lead to re-confirm). Confident: SF10, SF11 → `accuracy.json` **N = 2, horizontal RMSE 35.0 m** (max 35.1). SF09, SF12, SF18/19 are visible but their IDs are ambiguous → excluded. **Cause, measured:** the 50 camera positions over this part form a line (150 m long, 4.2 m across-track spread), so the reconstruction can roll about the flight line; both shifts are 34.7–34.8 m across-track, 3–5 m along-track. Not a GPS-accuracy number: a capture-geometry failure. **Capture-protocol rule: never map from one straight line; fly ≥ 2 parallel lines.** Proper accuracy needs a neighbouring strip (likely `F01-4`, 1.89 GB). Datum (NAD83 vs WGS84, ~1–1.5 m) still unconfirmed, negligible at this error | Claude measured |
| 31 Oct 04:40 | **Step 8 (full tier, single strip):** run `2026-10-31_0337_southfork_f01_5_full`, done, 66.6 min **incremental** (reused matching), peak 7.01 GiB, 9.07 ha, DSM/DTM at 0.10 m (range ~1159–1359 m). DTM vs 823 RTK ground points: mean +58.6 m, std 7.6 m, tilt −8.4° across track. Focal length and flying height in the model are right; the images' GPS altitudes read ~146 m above ground vs ~110 m stated, so the vertical offset comes mostly from GPS altitude + roll tilt. Full write-up: `docs/validation.md` | Claude measured |
| 3 Nov 02:55 IST | **Extension to 3 Nov; no re-flying (lead).** Teammate withdrew the BRISQUE table (merged). Demo video recorded from the laptop app (`docs/demo/typhon_demo.mp4`). Search for more checkpoints: F01-4 has none left (chalk marks unreadable, SF14 off the map); F02-2 processed as validation Run 4 (43.6 min, one line, map in two disconnected patches, 0 checkpoints confirmable). Block stays ±6.1 m at N=3 | Lead (scope), Claude (runs) |
| 3 Nov 22:20 IST | **Final evening (lead): finish our side, push to main at 23:55; friend builds the video in Antigravity from `docs/demo/video_script.md`.** Added the live field-report loop (phone report → road recolours, cut-off count updates, notice) and fixed `/field` defaulting to the mock project. Added a `first` tier: 50.3 min for the 248-photo block (vs 145.6), ±8.4 m at 2 checkpoints and slightly warped, so for seeing, not measuring (validation Run 5) | Lead (scope), Claude (build, runs) |
| 4 Nov 22:35 IST | **Submission reopened to 5 Nov 06:00 (lead).** Push to main at 05:30, code freeze 04:30. Added a PIN for phone field reports; a `middle` tier run on the block (speed vs error); Thar and Dhruv dimensions sourced. Checkpoints can't grow: every public flight we hold is used | Lead (scope), Claude (build, runs) |
| 31 Oct 23:10 IST | **Typhon v2: one look across site, dashboard and deck** (lead). Lead's fonts everywhere (Space Grotesk headings/labels, Inter body); palette = brand sand/stone paper + the deck's navy #0F1E3D (ink, dark surfaces), blue #2A4EA8 (data, links), lime #B5D334 (small highlights); road status colours unchanged. Lead's logo on home, footer and deck. About and Drone data now sit below the hero on the home page ("Explore" scrolls into them); the separate pages were removed. Field page recoloured (variables only). **Teammate's final push merged** (verification screenshots: phone over hotspot, QGIS, Google Earth, PDF) **except the BRISQUE "benchmark"**: its script only printed a hand-written JSON, the test asserted those numbers, and the figures are internally inconsistent (33 TP/6 FP → precision 0.846, not 0.833); review notes added to her report; not used anywhere | Lead (design), Claude (build, review) |
| 31 Oct 22:40 IST | **Lead's design direction for the content pages and deck: "field ticket" style** (lead's mockup: notched tickets, navy/paper/lime, halftone, typewriter text, condensed italic titles). Mockup copy not used (it described a different, AI cyclone product with invented figures); text and numbers are ours. New pages `about/` and `neo2/` (Drone data: how we filmed, what we used, result, lessons); halftones made from our own images only (`web/scripts/halftone.py`). Home: "Insights" link removed, old About text band removed. Dashboard: guided tour (12 steps, Guide button; `src/tour.js`). Public read-only snapshot on GitHub Pages (`gh-pages` branch) so judges get a link; field reports and measuring need the laptop and say so | Lead (design, go), Claude (build) |
| 31 Oct 20:45 IST | **Teammate follow-up 3 merged into `main`** (`teammate` @ `275d647`: F1 honest access reasons, F2 PDF/KMZ fit and labels, F3 `/field` restyle, F5 T14 "estimated quality indicator" layer, report in `docs/teammate_report.md`; all inside her folders, no conflicts; 102 pass, 2 skipped for environment). Checked on the real block: no reason says "cut off", "passable" or "reachable by all"; base reads "active responder staging base"; PDF fits the orthophoto with title, Processed/Capture/Basis lines and 16 inside / 482 outside. Our fixes at merge: `accuracy.json` per-point now carries the surveyed lon/lat (recomputed, every number identical) so the PDF draws the 3 checkpoints; PDF metadata box wraps instead of running off the page; Act card shows "cut off" and "access unverified" counts separately (her new contract). Phone test of `/field` done by the teammate on her laptop's hotspot (her report, V3); her screenshots (phone, QGIS, Google Earth) are not in git, likely under ignored `data/`. Her BRISQUE vs standard-check scores (report §5) have no saved results file, so they are not used in README or slides | Lead (merge rule), Claude (review, fixes) |
| 31 Oct 18:35 IST | **Teammate push merged into `main`** (`teammate` @ `001c70f`: exports E1–E6, sitrep, WorldPop, ML groundwork, sources with tests; all inside her folders, no conflicts, 99 tests pass). Run on the real block: exports work (accuracy line reads ±6.09 m); advisor marks all 498 segments unknown, correctly, but its reasons say "cut off"/"reachable by all vehicles" for places whose roads are only unknown, and the A3 PDF is zoomed to all OSM roads with a processing time labelled as survey time → `docs/teammate_followup_3.md` (push by 20:15 IST). Our Act card now says "unverified access" when nothing is blocked. Neo 2: deck only (lead). Pushed; fresh clone installs, builds, tests pass | Lead (merge, push), Claude (review) |
| 31 Oct 17:50 IST | **Neo 2 video run done** (`2026-10-31_1111_neo2_0149_quick`): 220 frames, **67.7 min**, peak 8.24 GiB, 4.32 ha extent at 5 cm. 214/220 frames reconstructed but in **7 pieces** joined by GPS only. The sports ground maps cleanly; surrounding buildings and trees are smeared (oblique views over a smoothed surface), so the extent overstates the usable map. No checkpoints → no accuracy figure. Written up as validation Run 3. Not added to the app's site picker (lead's call) | Claude measured |
| 31 Oct 17:45 IST | **Checkpoint datum confirmed: NAD83(2011)** (USGS metadata XML, downloaded by the lead). `accuracy/datum.py` converts checkpoints to WGS84 (ITRF2020, epoch 2024.33; 1.52 m W, −0.63 m) before comparing; the map is not touched. **Block horizontal 6.42 → 6.09 m** (east–west error 1.07 → 0.59 m; the ~6 m north offset is the map); strip 35.01 → 34.21 m; absolute RMSE_V 44.08 → 44.70 m; relative 1.09 m unchanged. Old results kept as `accuracy.pre_datum.json`. Samples regenerated | Claude measured |
| 31 Oct 17:03 IST | **Lead synced the laptop clock to IST** (from here on, times are real IST). The Neo 2 run `2026-10-31_1111_neo2_0149_quick` spans the change: its `started_at` is old-clock, `ended_at` new-clock, so use its `total_seconds` (measured with a monotonic clock, unaffected), not ended − started | Lead |
| 31 Oct ~17:00 IST | **Block full tier done** (`2026-10-31_0819_southfork_f01_4_full`: 171.4 min incremental, peak 11.0 GiB, 13.19 ha). Vertical: absolute RMSE_V 44.08 m at 3 targets; DTM vs 326 ground points +42.86 m offset, **1.09 m relative spread** → `accuracy/vertical.py` adds `vertical_relative`; measure/ and roads/ use it for height/volume tolerances. 16 trail segments in the map, all <45% visible → unknown. No landing zone met the rules. Block terrain, thumbnails and `samples/southfork_f01_4/` made; app now runs on the block. Neo 2 run (220 geotagged frames) started. Follow-up 2 sent to teammate | Claude measured |
| 31 Oct 14:30 IST | **Clock correction:** the laptop clock runs ~5 h 40 min behind IST; every time in this log and in `data/runs/` before this row is laptop time (add ~5:40 for IST). Real time now 14:30 IST → code freeze 21:30 IST is ~7 h away. Revised order: design colour pass (now) → full tier done ~16:15–16:45 IST → vertical accuracy, block roads/3D, teammate follow-up 2 → Neo 2 video run → PPT last. Lead approved the dashboard design; teammate will push her follow-up 1 work in a couple of hours | Lead |
| 31 Oct 08:30 | **Block run (USGS F01-4, 5 parallel lines), quick tier:** run `2026-10-31_0546_southfork_f01_4_quick`, 248/248 images in 1 component, **145.6 min**, **peak 8.61 GiB**, **12.94 ha** → ~11.2 min/ha. GPU feature extraction confirmed (`ROOT_SIFT_GPU`, 149 s for 248 images vs ~5 s/image on CPU in the strip run); matching + reconstruction dominate (opensfm 110 min, incl. ~20 min undistorting through the Docker file mount). **Accuracy: N = 3 checkpoints (SF16, SF17, SF18), horizontal RMSE 6.42 m, max 7.88 m**, a consistent ~1 m W / 5–8 m N shift (part may be the unconfirmed NAD83/WGS84 datum, ~1–1.5 m). SF15, SF19, SF20 not identifiable at 5 cm. Full tier started (reusing matching). Lead freed 22 GB on C: | Claude measured |
| 31 Oct 08:20 | Lead's hero image (illustration, captioned as such) and logo SVGs added; logo recoloured for light UI by `web/scripts/make_logo.py` | Lead |
| 31 Oct 07:35 | **Product name: Project Typhon** (team name stays Vortex; repo name unchanged; internal code names like `VORTEX_*` unchanged). Brand kit v1.0 adopted for the UI; status colours chosen by Claude within the brand (open green solid, partial amber dashed, blocked red thick + ✕, unknown grey dotted, needs-verification ocean ring). Landing page kept: lead supplies one hero image; Claude overlays the rest. Mockup data is decorative only: the app shows only our measured values | Lead |
| 31 Oct 06:30 | **Round 1 deliverable = PPT + GitHub link**; no rehearsals (lead). Step 11 (UI) is design-led: the lead designs, Claude implements against `docs/ui_layout_brief.md`; visual decisions stay with the lead | Lead |
| 31 Oct 05:45 | **Teammate round 1 reviewed and merged into `main`** (branch `teammate` @ `be4ed92`, 9 commits, 03:44–04:28): all files inside her folders; rules labelled "never AI"; 59 `PLACEHOLDER`s; no runtime internet or CDN; 68 tests pass on `main` after merge (2 skipped). Not verified for real: Neo4j (sandbox), Wayanad prefetch, field page on a phone, ML gate; some sources are home-page only. Lead's question "was her work limited?": no; she finished all Must and Should items as code quickly; the gaps are verification. | Lead (merge rule), Claude (review) |
| 31 Oct 05:50 | **Exports move to the teammate** (`export/`), so the lead's side keeps pipeline, accuracy, measure, roads and web. `docs/teammate_followup_1.md` lists everything she can finish without us; follow-up 2 comes when our real outputs exist | Lead |
| 31 Oct 05:40 | `F01-4` (248 images) downloaded and extracted: a **block of 5 parallel flight lines** over targets SF15–SF20 (6 targets, all seen by ≥ 3 images). Quick tier started on it with `--feature-type sift` (GPU test); first attempt failed in 0.4 s because Docker Desktop had stopped while the laptop slept, relaunched | Claude |
| 31 Oct 02:20 | Rebalance: `roads/` (T9) and the data panels (T10) move back to the lead. Reason: T9 needs our DSM and `measure/` code and fits our ODM waits; panels keep all of `web/` with one owner who also does styling. Her 8 Must items can all start on mock data now | Lead |
| 31 Oct 02:00 | Step 4 done → `data/raw/neo2/video_report.json` (+ `<clip>_track.csv`). Videos moved from Downloads. **GPS:** 3363/3363 frames (clip 0148) and 10615/10615 (clip 0149); flight extent 29.5 × 37.1 m and 50.9 × 74.0 m; paths 87.6 m and 390.3 m. Altitude field reads 299.8–325.8 m, reference unknown (not used for anything yet). **Brightness:** median luma 98.7 / 101.2 of 255, 0 of 20 frames dark. **Sharpness:** Laplacian variance median 27.1 / 34.5; 18 of 20 frames per clip under the PLACEHOLDER blur threshold of 100. ISO (inferred field) reached 4250 / 6400, so night noise reduction likely softens detail. Threshold is uncalibrated, so this is a warning, not a verdict: the video tier run decides | Claude measured |
| 31 Oct 02:00 | Step 9 approach changed: since the GPS exists, extract frames ourselves, drop bad ones (standard check now, teammate's `image_quality.json` later), write GPS into each frame's EXIF, then run ODM on images. This replaces ODM's MP4+SRT path and gives the video map a real position and scale (consumer-GPS accuracy, to be stated) | Claude; lead to confirm |

## Bug table
| # | Bug | Owner | Status |
|---|---|---|---|
| — | none yet | | |

## Placeholders (until sourced)
Pinned image tags (ODM, Neo4j) · vehicle passability thresholds · helicopter dimensions and slope limit · bridging panel rule · working-space requirement · road width defaults by class · `obstruction_min_m`, `bank_drop_min_m` · population source (teammate).
