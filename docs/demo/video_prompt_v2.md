# Prompt for the video, version 2 (5 Nov 2026)

Paste everything below the line into Antigravity on the video laptop.

---

## 1. Context

You are revising the 90-second demo video for **Project Typhon** (team Vortex, hackFront India 2026, problem statement T8.2 "The First Map After The Landslide"). Typhon is software that turns a consumer drone's photos or video into a map on one ordinary laptop, with no internet, and then says, for each vehicle (fire truck, ambulance, 4x4, foot team), whether each road can be used. Every measurement carries its error.

You made version 1 (`VID-20261105-WA0000.mp4`, 90.0 s, 1920x1080). Its look, colours, fonts, wipes and end card are good: **keep them**. A reviewer found it hard to follow: text flashes by, the app screens are too dense to read, and it plays as a feature checklist instead of a story. Version 2 adds a voiceover, slows down, focuses on fewer things, and fixes four wrong numbers.

**Files you have:**
- `VID-20261105-WA0000.mp4`: your version 1 (the base to edit).
- `docs/demo/video_script.md`: the original script, colour tokens, fonts, and the numbers sheet with sources (section 4). Its rules still apply.
- `docs/demo/typhon_demo.mp4`: screen recording of the real app (its burned-in caption, bottom ~90 px, must be cropped or covered).
- `report_loop/phone.mp4` and `report_loop/dash.mp4`: a phone sends a field report, and the dashboard recolours the road and shows a notice (submit at ~6 s in phone.mp4; notice at ~16 s in dash.mp4).

## 2. What you may and may not change

- **May change:** the timeline, pacing, captions, card text, transitions, and audio (voiceover and music).
- **Must keep:** the theme (navy #0F1E3D, lime #B5D334, paper #EBE2CC, blue #2A4EA8, Space Grotesk / Inter), the logo, the end card and its URLs.
- **Must not change:** any number except the four fixes in step 1, and must not add new numbers. Every number on screen or in the voiceover must appear in section 5 below.

## 3. Hard rules

1. **No invented numbers or claims.** If something is not in section 5, it does not go in the video.
2. **Never say or show:** "AI", "autonomous", "automates the flight path", "high-precision", "survey-grade", "professional accuracy", "real-time", "instant", "life-saving" (it has not been used in a real rescue), "exactly which road is clear".
3. The South Fork data is **USGS public data, not our footage**: keep the small "USGS PUBLIC SURVEY · NOT OUR FOOTAGE" line wherever its map appears.
4. One caption line on screen at a time, at most about 8 words, held at least 2.5 s.
5. When you show an app screen, zoom to one part of it (a road, a number, a panel) and dim or blur the rest. Hold each app shot at least 4 s.
6. Keep the captions even with the voiceover: many judges watch muted.
7. If something below is impossible with the tools you have, **stop and tell the lead** instead of improvising.

## 4. Steps

**Step 1. Fix the four wrong things in version 1:**

| Where in v1 | Now shows | Change to |
|---|---|---|
| ~0:28 clock beat | "Map ready in 2 h 26 min" | "**First measurable map in 80 min.**" Mono line: `248 PHOTOS · 13.1 HA · 16 GB LAPTOP, RTX 4050 · 80.2 MIN`. Sweep the clock hand to 80 min. (A new setting, tested on 4 Nov, is as accurate as the old 2 h 26 min one: 6.06 m vs 6.09 m at the same 3 checkpoints.) |
| ~0:50 five-line card | counter passes through "16.1 m" before "6.1 m" | Count **up from 0** to 6.1 m, or show 6.1 m without counting. A paused frame must never show a wrong number. |
| ~0:62 Neo 2 beat | "242 frames → 220 sharpest" (and "220 frames → 220" a second later) | "**880 frames → 220 sharpest → map in 68 min**" |
| ~1:14 offline beat | "95 requests · 0 left the laptop" | "**99** requests · **0** left the laptop" |
| ~1:18 Fly / Map / Decide cards | FLY: "Autonomous & Manual Flights" | FLY: "Any consumer drone"; MAP: "Offline map + 3D heights"; DECIDE: "Road status per vehicle" |

**Step 2. Restructure into 6 parts that follow the voiceover in step 3.** Drop the QGIS/print beat to a 2-second mention, and drop the 3D beat into a 3-second cutaway inside part 4. The **hero** is part 5: the phone report changing the dashboard. It is the easiest thing to understand and it is real.

**Step 3. Record the voiceover** (calm, documentary pace, about 130 words per minute; a short pause after part 2). It runs about 170 words: about 78 s at that pace, leaving room for pauses. Do not speed it up to fit. Use exactly these words:

| Time | Part | Voiceover | On screen |
|---|---|---|---|
| 0:00–0:09 | 1. Stakes | "A landslide cuts off a mountain village, and the old map is suddenly wrong. Which roads can still take an ambulance?" | Keep v1's navy opening, road line breaking, BLOCKED stamp |
| 0:09–0:20 | 2. Problem | "A new satellite image can take days. A survey crew is at risk on unstable slopes. But a small drone is often already in the jeep." | Keep v1's satellite vs drone split |
| 0:20–0:32 | 3. Typhon | "Project Typhon turns that drone's photos or video into a map on one ordinary laptop. No internet. No cloud. No ground markers." | Logo wipe, then the FLY → MAP cards, then the fixed 80-min clock |
| 0:32–0:50 | 4. Decide | "On this USGS test site, the first measurable map took about eighty minutes. Each road is checked for each vehicle: fire truck, ambulance, four-by-four, foot. Where trees hide the road, Typhon says unknown." | Zoom into one road on the dashboard; vehicle picker; "UNKNOWN" stamp under trees; 3-s 3D cutaway |
| 0:50–1:05 | 5. Proof, then hero | "Every measurement carries its error. One straight flight line: thirty-four metres off. Five parallel lines: six. And ground teams report back by phone, over the laptop's hotspot." | "34 m → 6 m" card (counter fixed), then phone.mp4 beside dash.mp4: tap Submit, the road recolours, the notice appears |
| 1:05–1:18 | 6a. Field | "The dashboard picks up each report within seconds. Our own drone video works too, and maps open in QGIS and Google Earth." | Hold on the dashboard notice; Neo 2 beat (fixed numbers); 2-s QGIS flash |
| 1:18–1:30 | 6b. Close | "No signal in the valley? Nothing changes. Fly. Map. Decide. Project Typhon: the first map after the landslide." | Offline beat (99 requests), Fly / Map / Decide cards (fixed text), end card |

**Step 4. Audio mix.** Voice at about −16 LUFS; music (if any) about 18 dB under the voice and licence-free. No sound effects louder than the voice. Version 1's audio track was completely silent, so this step is new.

**Step 5. Check your own work** against `CHECK.md` (write it):
- every number on screen and in the voiceover, with its line in section 5;
- a list of the banned words from rule 2, confirming none appear;
- frame grabs at 0:05, 0:25, 0:40, 0:55, 1:10 and 1:25;
- the total length (must be 90.0 s or less) and the loudness reading.

## 5. The only numbers allowed (all measured on the Typhon laptop; sources in `docs/validation.md`)

| Number | Meaning | Source |
|---|---|---|
| 248 photos, 13.1 ha | USGS South Fork block, 5 parallel flight lines | validation Run 6 |
| 80.2 min (say "about eighty minutes") | first measurable map, new "middle" setting | validation Run 6 |
| 6 m (6.06 / 6.1 m) | horizontal error, 5 parallel lines, 3 checkpoints, no ground control | Runs 2 and 6 |
| 34 m | horizontal error, one straight line, 2 checkpoints | Run 1 |
| ±1.1 m | heights relative to nearby ground, 326 surveyed points | Run 2 |
| 59.40 ± 8.62 m | span across the debris channel | demo video, Measure tool |
| 880 → 220 frames, 68 min | our own DJI Neo 2 video made into a map | Run 3 |
| 99 requests, 0 left the laptop | offline check, 3 Nov | `web/scripts/offline_check.mjs` |
| about 3 s ("within seconds") | dashboard picks up a phone report | `web/scripts/report_loop_test.mjs` |
| 16 GB laptop, RTX 4050 | the machine all of the above ran on | README |

Not allowed: "under two hours" for the old setting, "2 h 26 min" as the headline (it is now the slower option), any accuracy figure for the Neo 2 map (it has no checkpoints), any count of lives, people or rescues.

## 6. If you use an AI voice (e.g. ElevenLabs)

- Check the plan's terms. Some free plans require credit to be given and limit use; if so, add the credit line to the end card's small text.
- Tell the lead which tool and voice you used, so it goes into `docs/AI_DISCLOSURE.md` with the music's licence.

## 7. Definition of done

- `typhon_v2.mp4`: 1920x1080, 30 fps, 90.0 s or less, voiceover audible, captions present.
- `CHECK.md` and the six frame grabs.
- The four fixes in step 1 are visible in the frame grabs or in `CHECK.md`.

## 8. Time limit

Finish by **04:30 IST on 5 Nov** (the submission closes at 06:00). If you cannot finish everything, deliver in this order: (1) the four number fixes on version 1, with no other change; (2) plus the voiceover; (3) plus the restructure. **Send (1) first, as soon as it is ready,** so there is always a correct video to upload.
