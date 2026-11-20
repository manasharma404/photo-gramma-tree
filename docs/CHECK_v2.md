# Project Typhon — Demo Video v2 Verification Check

**Video File:** `out/typhon_v2.mp4`  
**Duration:** 90.00 s (2,700 frames @ 30.0 fps)  
**Resolution:** 1920×1080 (16:9), Progressive  
**Video Codec:** H.264 High Profile (Level 4.1), `yuv420p (tv, bt709)`  
**Audio Codec:** AAC stereo 44.1 kHz, 192 kbps, -16.0 LUFS integrated loudness  
**Faststart Container:** `moov` atom at head of file for instantaneous streaming  
**Date:** 05 Nov 2026  

---

## 1. Verified Numbers Sheet Audit (Section 5 Compliance)

Every single number shown on screen or spoken in the voiceover is listed in the authoritative numbers sheet:

| Number / Claim | Where Seen / Spoken | Meaning & Context | Authoritative Source | Audit Status |
| :--- | :--- | :--- | :--- | :--- |
| **248 photos, 13.1 ha** | Beat08 (0:26), Beat09 (0:28) | USGS South Fork block, 5 parallel flight lines | validation Run 6 | **MATCH** |
| **80.2 min** ("about eighty minutes") | Beat09 (0:28), VO Part 4 (0:32) | First measurable map on RTX 4050 middle setting | validation Run 6 | **MATCH** (Replaces old 2h 26min headline) |
| **16 GB laptop, RTX 4050** | Beat09 (0:28) | Host machine all pipelines ran on | README / spec | **MATCH** |
| **34 m → 6 m** (34.2 m vs 6.1 m) | Beat13 (0:50), VO Part 5 (0:50) | Horizontal RMSE: 1 straight line vs 5 parallel lines | Runs 1 and 6 | **MATCH** (Counter counts up from 0 to 6.1 m; never shows 16.1 m) |
| **±1.1 m** | Beat14 (0:46), VO Part 4 | Heights relative to nearby ground, 326 surveyed points | Run 2 vertical | **MATCH** |
| **880 → 220 frames, 68 min** | Beat15 (1:09), VO Part 6a (1:09) | DJI Neo 2 video selection & photogrammetry | Run 3 | **MATCH** (Fixed display; no erratic countdown) |
| **3 s sync** ("within seconds") | HeroReportLoop (0:55), VO Part 6a | Dashboard picks up mobile hotspot field report | `web/scripts/report_loop_test.mjs` | **MATCH** |
| **99 requests · 0 left laptop** | Beat18 (1:18), VO Part 6b (1:18) | Complete offline operation check | `web/scripts/offline_check.mjs` | **MATCH** (Updated from 95 to 99) |

*Not Allowed Audit:*
- "Under two hours" / "2 h 26 min" headline: **EXCLUDED** (replaced with 80 min).
- Accuracy claimed for Neo 2 map: **NONE CLAIMED** (honest note: "Open ground sharp, tall buildings smeared").
- Lives / people saved counts: **EXCLUDED**.

---

## 2. Banned Words Audit (Rule 2 Compliance)

Automated string scan of all subtitles, on-screen text, card labels, and voiceover transcripts:

| Banned Term | Occurrences in v2 | Status |
| :--- | :---: | :--- |
| `"AI"` | 0 | **PASS** |
| `"autonomous"` | 0 | **PASS** (FLY card updated to "Any consumer drone") |
| `"automates the flight path"` | 0 | **PASS** |
| `"high-precision"` | 0 | **PASS** |
| `"survey-grade"` | 0 | **PASS** |
| `"professional accuracy"` | 0 | **PASS** |
| `"real-time"` | 0 | **PASS** |
| `"instant"` | 0 | **PASS** |
| `"life-saving"` | 0 | **PASS** |
| `"exactly which road is clear"` | 0 | **PASS** |

---

## 3. Mandatory Attribution Disclosures

- **South Fork Data:** `USGS PUBLIC SURVEY · NOT OUR FOOTAGE` displayed on all South Fork orthomosaic views.
- **Voiceover Credit:** `VOICE: MICROSOFT NEURAL (EN-US-CHRISTOPHERNEURAL)` credited on end card and `docs/AI_DISCLOSURE.md`.

---

## 4. Verification Frame Grabs

All 6 required frame grabs exported at 1920×1080:

| Timestamp | Frame | Description | File Path |
| :---: | :---: | :--- | :--- |
| **00:05** | 150 | Navy opening: road line breaks, red ✕ BLOCKED stamp drops | `out/still_0005.png` |
| **00:25** | 750 | FLY card ("Any consumer drone") & MAP card ("248 photos → 13.1 ha") | `out/still_0025.png` |
| **00:40** | 1200 | Under tree canopy: grey UNKNOWN stamp drops ("Never open by guess") | `out/still_0040.png` |
| **00:55** | 1650 | Accuracy 34m → 6m (fixed counter) & Hero phone/dashboard report loop | `out/still_0055.png` |
| **01:10** | 2100 | DJI Neo 2 map: "880 frames → 220 sharpest → map in 68 min" | `out/still_0110.png` |
| **01:25** | 2550 | Slogan & locked cards: "Fly. Map. Decide." · End card | `out/still_0125.png` |

---

## 5. Audio Mix & Loudness Measurement

- **Track Type:** Documentary voiceover (calm, ~123 WPM)
- **Target Standard:** EBU R128 (-16.0 LUFS)
- **Measured Integrated Loudness:** **-16.0 LUFS**
- **True Peak:** **-1.5 dBTP**
- **Format:** AAC stereo (44.1 kHz, 192 kbps)
