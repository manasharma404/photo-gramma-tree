# Round 1 deck: content outline (not the design)

Content only; the lead does the visual design. Built around what the brief says judges reward: **measured positional error, processing time for a stated area on a normal laptop, output an agency can use.**
Every number below is from `docs/validation.md` / `README.md` (runs in `data/runs/`). Anything not measured yet is marked **PENDING**. Projector rules: one idea per slide, nothing under ~30 px, honest details go in the speaker notes.

---

### 1. Title
- **Project Typhon**: the first map after the landslide, on a laptop, offline
- Team Vortex · hackFront India 2026 · PS T8.2 · repo link: https://github.com/manasharma404/photo-gramma-tree
- Visual: hero image (`web/public/hero.webp`) + mark
- Notes: one sentence of what it does.

### 2. The problem
- A valley is cut off. Satellite pass days away, maybe cloud. Someone has a consumer drone.
- Missing: a way to turn that flight into a usable map **in the field, with no internet**
- Notes: the brief's situation, in our words.

### 3. What we built (one picture)
- Drone photos or video → map + height model → measurements → road status per vehicle → phones on a local network
- Visual: the pipeline diagram from the README, redrawn
- Notes: ODM in Docker on the laptop GPU; checkpoints never used to correct the map.

### 4. Judge criterion 1: positional error, measured
- **34.2 m → 6.1 m** horizontal, without ground control (USGS RTK checkpoints)
- One straight flight line (N=2) vs a block of 5 parallel lines (N=3)
- Visual: the two numbers big; checkpoint-error arrows screenshot (Accuracy tab)
- Notes: N is tiny vs ASPRS's 30, so these are prototype measurements. One line lets the model roll about it. Checkpoints converted from NAD83(2011) (USGS metadata) to WGS84 first, 1.5 m here; that took the block from 6.4 to 6.1 m, so the remaining ~6 m north offset is the map. Capture rule we derived: **never map from one straight line.**

### 5. Heights: what to trust
- Absolute heights off by **+43 m** (consumer GPS altitude)
- Heights relative to nearby ground good to **±1.1 m** (326 surveyed points)
- So volumes, pile heights, bank heights are usable; altitudes are not
- Notes: this is why every tolerance in the app uses the relative figure, and the UI says so.

### 6. Judge criterion 2: time for a stated area, on a normal laptop
- **12.94 ha in 145.6 min** (quick map, 248 images) · peak memory 8.61 GiB
- Height models: +171.4 min reusing the same matching · 13.19 ha · 11.0 GiB
- Laptop: i5-13420H, 16 GB RAM, RTX 4050 (state it plainly)
- Notes: single strip was 10.12 ha in 50.4 min; per-hectare rate depends on overlap. Neo 2 video run: **PENDING** (running now).

### 7. Judge criterion 3: output an agency can open
- Dashboard: map, 3D view, road status per vehicle (fire truck, ambulance, jeep, on foot), measuring tools
- Status by colour **and** line pattern (open / partial / blocked / unknown)
- Visual: dashboard screenshot (`data/screenshots/01_map_act.png`) + 3D (`04_3d.png`)
- Notes: everything served by the laptop; headless check found 0 of 81 requests leaving the laptop. Phone test: **PENDING** (`docs/phone_check.md`).

### 8. Honest "unknown"
- 16 trails under canopy: only 5–43% visible → marked **unknown**, not open
- No landing zone met the slope and clear-ring rules in this canyon
- Notes: a drone can't certify what it can't see; the tool says so. Thresholds are PLACEHOLDERs until sourced.

### 9. Measuring tools (click on the map)
- Span 59.4 ± 8.6 m · debris volume 67.6 ± 277 m³ · working space 1.5 × 2.0 m (fails)
- Every result carries its tolerance
- Notes: tolerances are large where the ground is rough or small; tool-vs-tape comparison **PENDING** (our survey flight was rained out).

### 10. Response advisor (teammate)
- Who is cut off, what reopens access first, per vehicle
- Wayanad 2024 scenario from cited reports, labelled as a scenario
- Numbers/screens: **PENDING** her push
- Notes: road states from reports, not drone-measured.

### 11. Our own footage: DJI Neo 2
- Video → 220 geotagged frames (GPS decoded from the clip's telemetry)
- Result: **PENDING** (the run reconstructed in several pieces; report what happened)
- Notes: altitude reference unknown → heights relative only.

### 12. What's real, what's next
- Real: USGS public data (labelled), our Neo 2 clip, all numbers from runs on this laptop
- Next (by 21 Nov): fly our own survey with ≥2 lines + our own checkpoints; tool vs tape; more checkpoints
- Repo link again
- Notes: AI use logged in `docs/AI_DISCLOSURE.md`; data licences in `data/LICENSES.md`.

---

## Screenshots needed
| For slide | File | Status |
|---|---|---|
| 1 | `web/public/hero.webp` | have |
| 4 | Accuracy tab with checkpoint arrows | retake at projector size |
| 7 | `data/screenshots/01_map_act.png`, `04_3d.png` | have; retake after teammate merge |
| 7 | Phone screenshots | PENDING phone test |
| 9 | One measurement result on the map | from `tools_test.mjs` run |
| 10 | Advisor panel | PENDING teammate |
| 11 | Neo 2 orthophoto | PENDING run |
