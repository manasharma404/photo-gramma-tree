# Project Typhon: demo video script (90 s)

For the motion-graphics video built in Antigravity. It borrows the *grammar* of the reference video (VeriFi AI, 34 s) and fills it with our product, our theme and only our measured numbers.

Inputs the builder gets:
- the reference video (34 s);
- `docs/demo/typhon_demo.mp4` (1 min 41 s, screen recording of the real app; snippet times below refer to it);
- the Typhon logo (wordmark from the lead; also inline in `web/src/icons.js`, `data-logo-full`);
- `data/screenshots/neo2/ortho_preview.png` (our Neo 2 map) and `docs/screenshots/map_a3_preview.png` (printable PDF map).

## 1. What we take from the reference
Analysed frame by frame (2 frames a second). Audio was not listened to; it is loud throughout (mean −16.6 dB), so it is most likely a music bed.

| Reference does | We do |
|---|---|
| One idea per beat, about 3 s each, no hard cuts: everything slides, fades or morphs | Same. Every beat boundary sits on a 2 s grid, so cuts land on the bar of a 120 BPM track |
| Dark opening with the problem, then a **circle wipe** to a light background for the answer | Navy opening (the landslide), then a **contour-ring wipe** (paper circle with 3 ring lines, like contour lines) to the paper map sheet |
| Caption = small dark pill at the bottom, one keyword in yellow | Caption = navy pill, one keyword in **lime**. Same as our app's demo caption |
| Two-line statements: line 1 dark, line 2 in the accent colour, revealed after a beat | Line 1 navy, line 2 **blue** (on paper) or **lime** (on navy) |
| Recreated UI cards (not screen recordings) that build item by item | Recreated cards for Fly / Map / Decide, plus real app snippets inside a laptop or phone frame |
| A **stamp** ("HELD") drops onto the key moment | Stamps: red **✕ BLOCKED**, grey **UNKNOWN**, navy **OFFLINE** |
| Two cards slide together at the end (detects + decides) | Three cards slide together: **Fly · Map · Decide** |
| End card: two-line slogan, logo, yellow pill CTA, tiny mono line | Same, with a lime **TRY IT →** pill and the site URL in mono |

## 2. Style
- **Colours** (from `web/src/styles/tokens.css`): navy `#0F1E3D`, navy-2 `#1B2F5C`, blue `#2A4EA8`, lime `#B5D334`, paper `#EBE2CC`, sand `#F5F1E6`, stone `#E6E1D6`, slate `#56607A`. Road status: open `#2E7D4F`, partial `#C98A12`, blocked `#B3261E`, unknown `#8C918A` (dotted).
- **Fonts:** Space Grotesk (headlines, captions, numbers), Inter (small text), any mono for source labels.
- **Map-sheet motifs** (our home page): dotted graticule (latitude/longitude lines), contour lines, compass rose, coordinate collar along the edges, survey route with waypoint dots, DSM ridge lines.
- **Text size:** headlines ≥ 72 px, captions ≥ 34 px, source labels ≥ 22 px at 1920×1080. Source labels stay on screen at least 1.5 s.
- **Motion:** ease-in-out (cubic), 400–600 ms per move; counters roll over 800 ms; stamps drop from 140% to 100% scale with a 2-frame shake; a slow 3% push-in on every held shot so nothing is ever static.
- **Sound** (if used): 120 BPM track, licence recorded; soft whoosh on wipes, a low thud on stamps, ticks on counters.
- **Location stamp:** `36.3448° N · 118.7580° W` is the debris channel we measure (South Fork, Sequoia & Kings Canyon, California).

## 3. The script
Times are mm:ss in the final video. "Snippet" times refer to `typhon_demo.mp4`. **That recording has its own caption pill burned in at the bottom centre (about the bottom 90 px of 900):** crop it off or cover it with the frame, so it never competes with the new captions. Text in quotes is exactly what appears on screen. **Lime** / **blue** mark the keyword.

### Act 1: the problem (navy)
| # | Time | Visual and motion | On-screen text | Transition out |
|---|---|---|---|---|
| 1 | 00:00–00:04 | Black fades to navy. The dotted graticule draws in from the left; the coordinate collar ticks in along the edges; `36.3448° N · 118.7580° W` types out in the corner | "A landslide takes the **road**." | Contour lines rise out of the graticule |
| 2 | 00:04–00:08 | A slate road line draws across the contours; at its middle a red **✕ BLOCKED** stamp drops with a thud | "…and the **map** goes with it." | Stamp and road blur and dim |
| 3 | 00:08–00:12 | Two lines, centred, line 2 revealed 1 s after line 1 | "Which road can still take an ambulance?" / "Rescuers need to know **today**." | Text slides up and out |
| 4 | 00:12–00:16 | Split screen. Left: satellite icon, its line fades to slate. Right: drone icon, its line pops in lime. At 15.0 s the **contour-ring wipe** opens from the compass centre and fills the screen with paper by 16.0 s | Left: "Next satellite image: days away." Right: "A drone: already in the **jeep**." | Contour-ring wipe |

### Act 2: the answer (paper map sheet)
| # | Time | Visual and motion | On-screen text | Transition out |
|---|---|---|---|---|
| 5 | 00:16–00:20 | Typhon logo draws in (stroke, then fill). Faint graticule and compass rose on the paper | "PROJECT TYPHON" / mono: "TEAM VORTEX · HACKFRONT INDIA 2026" | Logo shrinks to the top-left corner and stays as a watermark |
| 6 | 00:20–00:24 | Two lines, line 2 after 1 s | "Not a satellite. Not a survey crew." / "The **first map** after the landslide." (blue) | Line 2 slides left into a card |
| 7 | 00:24–00:28 | Card **FLY**: a survey route draws in five parallel lines with waypoint dots; a small drone glyph follows it | Card: "FLY" · Caption: "Any consumer drone. Photos or **video**." | Card slides left, next card enters right |
| 8 | 00:28–00:32 | Card **MAP**: 248 tiny photo thumbnails fly in and stack, then morph into the orthophoto (still from snippet 00:19). Counter rolls 0 → 248, then "12.94 ha" appears | Card: "MAP" · "248 photos → 12.94 ha" · Caption: "One laptop. No internet. **No ground control.**" · mono: "USGS PUBLIC SURVEY, SOUTH FORK CA, 2024 · NOT OUR FOOTAGE" | Orthophoto zooms out into a clock face |
| 9 | 00:32–00:36 | A clock hand sweeps; counter rolls to "2 h 26 min" | "Map ready in **2 h 26 min**." · mono: "248 PHOTOS · I5 LAPTOP, 16 GB, RTX 4050 · 145.6 MIN" | Clock shrinks into a laptop screen |

### Act 3: the proof (real app, inside a laptop frame on paper)
| # | Time | Visual and motion | On-screen text | Transition out |
|---|---|---|---|---|
| 10 | 00:36–00:40 | Card **DECIDE**, then a laptop frame tilts in (5°, settling flat) playing snippet **00:40–00:44** (vehicle buttons change, counts update) | Caption: "Pick who's going. Every road answers for **that vehicle**." | Push into the map area |
| 11 | 00:40–00:46 | Snippet **00:44–00:48** full frame, slowed. Tree glyphs drift over the trail lines, which turn grey-dotted. A grey **UNKNOWN** stamp drops at 43 s | "Under trees, we can't see the road." / "So we say **unknown**. Never open by guess." · mono: "16 TRAILS · 5–43% VISIBLE · 70% NEEDED TO DECIDE" | Grey dots morph into a measuring line |
| 12 | 00:46–00:52 | Snippet **01:08–01:17** sped to 6 s: a span is drawn across the debris channel and the result panel appears. Big counter overlays and rolls to the result | "**59.40 m ± 8.62 m**" · Caption: "Measure the debris channel. Every number carries its **error**." | The counter slides into a split screen |
| 13 | 00:52–00:58 | Split screen of two map tiles. Left: a single strip, visibly rotated off its outline, red offset arrow "34.2 m". Right: a five-line block sitting almost on its outline, blue arrow "6.1 m". Counter rolls 34.2 → 6.1 | "One straight line: 34 m off." / "Five parallel lines: **6 m**." · mono: "3 USGS CHECKPOINTS · NO GROUND CONTROL USED · PROTOTYPE MEASUREMENT" | Right tile lifts into 3D |
| 14 | 00:58–01:02 | Snippet **01:26–01:31** (3D terrain), slow orbit feel with the push-in | "3D from the **same photos**." / "Heights good to ±1.1 m." · mono: "RELATIVE TO NEARBY GROUND · 326 SURVEYED POINTS" | 3D shrinks into a polaroid-style card |
| 15 | 01:02–01:06 | Our own map card (`ortho_preview.png`) with the sharp sports ground highlighted. Counter "880 → 220" frames | "Our own drone video, made into a map." · "880 frames → 220 sharpest → map in **68 min**" · mono: "DJI NEO 2 · OPEN GROUND SHARP, TALL BUILDINGS SMEARED" | Card flips into a phone |

### Act 4: the field (phone)
| # | Time | Visual and motion | On-screen text | Transition out |
|---|---|---|---|---|
| 16 | 01:06–01:12 | A phone frame rises from the bottom, playing snippet **01:32–01:38** (field report page) | Caption: "Field teams report from a phone on the laptop's **hotspot**." | Phone slides right |
| 17 | 01:12–01:16 | **OPTION A, only if the report loop is built and recorded:** phone taps "Blocked"; beside it the dashboard road turns red and a **✕ BLOCKED** stamp drops. **OPTION B (default):** the printable PDF map (`map_a3_preview.png`) slides out of the laptop like paper from a printer | A: "One tap. The road turns **red**. The plan updates." · B: "Print it, or open it in **QGIS and Google Earth**." | Everything fades except a Wi-Fi glyph |
| 18 | 01:16–01:20 | The Wi-Fi glyph gets a slash; a navy **OFFLINE** stamp drops; counter rolls "95 requests · **0** left the laptop" | "No signal in the valley? **Nothing changes.**" · mono: "OFFLINE CHECK, 3 NOV · 95 REQUESTS, 0 OUTSIDE THE LAPTOP" | Three cards enter |

### Act 5: close
| # | Time | Visual and motion | On-screen text | Transition out |
|---|---|---|---|---|
| 19 | 01:20–01:24 | The FLY, MAP, DECIDE cards slide in and lock together with a small bounce (reference's "detects + decides") | "**Fly. Map. Decide.**" | Cards collapse into the logo |
| 20 | 01:24–01:30 | End card on paper with faint graticule. Two lines, logo, lime pill, mono links. Hold; fade to navy over the last 1 s | "The first map after the landslide." / "Project **Typhon**." · Pill: "TRY IT →" · mono: "manasharma404.github.io/photo-gramma-tree · github.com/manasharma404/photo-gramma-tree" | Fade to navy |

## 4. Numbers sheet (the only numbers allowed on screen)
| On screen | Exact value | Why it matters | Source |
|---|---|---|---|
| 248 photos → 12.94 ha | 248 images, 12.94 ha orthophoto | the size of a real survey we mapped | `docs/validation.md`, Run 2 |
| 2 h 26 min | 145.6 min, quick tier, from scratch | a map the same day, on a laptop a team can carry | Run 2 |
| 59.40 m ± 8.62 m | span across the debris channel | a measurement that says how sure it is | `web/scripts/tools_test.mjs`, demo video |
| 34 m → 6 m | RMSE 34.21 m (2 checkpoints) vs 6.09 m (3 checkpoints) | flight pattern alone makes the map over 5× more accurate, with no ground control | Runs 1 and 2 |
| ±1.1 m heights | std 1.09 m vs 326 surveyed ground points, relative heights | debris piles and banks are measured against nearby ground, where this holds | Run 2, vertical |
| 16 trails, 5–43% visible, 70% needed | trails under canopy all marked unknown | the tool refuses to guess | Run 2, roads |
| 880 → 220 frames, 68 min | 67.7 min, our DJI Neo 2 clip | our own footage works end to end | Run 3 |
| 95 requests, 0 outside | offline check, 3 Nov | it truly runs with no internet | `web/scripts/offline_check.mjs` |

**Never on screen:** "AI", "real-time", "instant", "survey-grade", "certified", "accurate to 6 m everywhere", any number not in this table, stock disaster footage presented as ours, Wayanad shown as drone-measured. Absolute heights are +43 m off; never show an absolute height.

## 5. Prompt for the Antigravity agent
Paste everything between the lines.

---
**Context.** You are making a 90-second product video for Project Typhon (hackathon team Vortex). Typhon turns consumer drone photos into a map, measurements and road status per vehicle, offline on one laptop. Read, in this order: (1) this script, all of it; (2) the reference video, for pacing and transitions only; (3) `typhon_demo.mp4`, the real app, for snippets at the times the script gives; (4) the logo and the two screenshots.

**Files.** Work only in a new folder `typhon_video/`. Do not change any other file on this computer. Use Remotion (React video) so timings are frame-exact; if Remotion cannot be set up, use HTML/CSS animation with fixed timings and record it at 1920×1080, 30 fps.

**Hard rules.**
1. Every number on screen comes from section 4 of the script, written exactly as there. Do not round differently, invent, or add numbers.
2. Every mono source label in the script appears for at least 1.5 s.
3. Do not use the words in "Never on screen".
4. Colours and fonts only from section 2.
5. Beat 17: use Option B unless you were given a recording of Option A.
6. Ask before downloading anything other than npm packages and Google Fonts. Music only if you are given a licensed track; note its licence in `typhon_video/CREDITS.md`.

**Steps.**
1. Set up the project at 1920×1080, 30 fps, 2700 frames (90 s).
2. Build the shared pieces: caption pill, two-line statement, stamp, counter, graticule background, contour-ring wipe, laptop frame, phone frame.
3. Build beats 1–20 in order, at the times given; check each against the script's text before moving on.
4. Cut the snippets from `typhon_demo.mp4` at the given times; speed changes as stated.
5. Render `typhon_video/out/typhon_90s.mp4` (H.264). Export stills at 00:02, 00:22, 00:55, 01:27 as PNG.
6. Write `typhon_video/CHECK.md`: for each beat, its start/end frame and the exact on-screen text, so the team can check it against the script.

**Done means:** a 90.0 s (±0.2 s) 1920×1080 MP4, all 20 beats in order, text matching the script word for word, all source labels visible, `CHECK.md` and the four stills present.

**Time limit:** 3 hours. If something is impossible (a snippet won't cut, a font won't load, a transition can't be built), stop and say what and why, instead of improvising a different design or different numbers.
---

## 6. After the video
- Add a row to `docs/AI_DISCLOSURE.md`: video built with Antigravity from this script.
- Record the music licence (if any) in `data/LICENSES.md`.
- Check the render against section 4 before submitting.
