# Fallback video: storyboard (45 seconds)

**Status: draft, 17 Nov. The lead approves the wording.** This video is a fallback for the finale. It is only submitted if every line in "Must be true before submitting" is true on the day.

- Scene file: `docs/demo/motion/fallback.html`. Render: from `web/`, `MOTION_SCENE=fallback.html node scripts/motion_render.mjs ../docs/demo/motion/out/typhon_fallback_45s.mp4` (about 30 minutes).
- Quick look at single frames: `bash docs/demo/motion/check_stills.sh fallback.html 4.9,20.5,33.2`.
- No sound. Voiceover, music, the team clip and our own flight footage are added by the lead.

## The story in one line
A real slide on the Kedarnath road → the old map is wrong → Typhon → what we measured and what it buys → the two decisions → back to the road → logo.

## Scene by scene
| Time | Scene | Words on screen | Picture |
|---|---|---|---|
| 0.0–6.0 | 1. The case | "19 May 2026. Landslides cut the road to Kedarnath." / "Rescue teams had to bring more than 10,000 stranded pilgrims across the debris." / counter to "10,000+", "Pilgrims stranded by one blocked road" | A road draws across, debris falls on it, people collect behind the gap. A drawing, not a map of the place. |
| 6.0–11.5 | 2. The problem | "Every map they carry shows the valley before the slide." / "Which roads still hold? Unknown." | Rows of outlined UNKNOWN drifting. A lime line opens into the title. |
| 11.5–15.0 | 3. Title | "TYPHON." / "The first map after a landslide, from one small drone." | Sand title card. |
| 15.0–20.9 | 4a. Speed | "The map grows while the drone is still in the air." / 248 photos placed, about one a second / rough map ready in about 5 min / detailed map takes 80 min / rough map is off by about 12 m / **"Rescue teams start reading the ground before the drone lands."** | Our real South Fork surface model rising; the real flight path. |
| 20.9–26.0 | 4b. No ground crew | "Height differences come out right to about one metre." / ±1.1 m against 326 surveyed ground points / survey markers placed: none / enough to size a debris pile / **"Nobody walks onto the slide before the map exists."** | Same model, camera still turning. |
| 26.0–37.5 | 5. The decision | "Typhon turns the map into a graph of roads and villages, then answers two questions." / "Question 1 · Clear first: which blocked road, once cleared, reconnects the most people?" / "Question 2 · Fly next: which unknown road is worth the next flight?" | A small road graph: open, blocked, unknown. The blocked road lights up and three villages reconnect; then a drone flies the unknown road. Labelled as an illustration. |
| 37.5–41.0 | 6. The close | "When the next road is cut, the first map should take minutes." | The cut road again; a drone flies along it. |
| 41.0–45.0 | 7. Logo | Typhon logo / "The first map after the landslide." / "Team Vortex · hackFront India 2026 · Problem statement T8.2" | Sand card with the lead's logo (`web/src/assets/logo-lockup.svg`). |

Labels that stay on screen: scene 1 "Source: SDRF figures reported by ANI, 20 May 2026"; scene 4 "Measured on a replay of a USGS survey flight · not our footage"; scene 5 "Illustration of the method · not a screen from the app".

## Where each number comes from
| On screen | Source |
|---|---|
| 19 May 2026, Sonprayag to Gaurikund, more than 10,000 pilgrims | The Watchers, 20 May 2026, citing SDRF through ANI: https://watchers.news/2026/05/20/over-10-000-pilgrims-rescued-after-landslides-disrupt-kedarnath-route-india/ . Business Standard's headline gives the same figure; its page could not be opened from here (HTTP 403), so it is not our source. Read on 17 Nov 2026. |
| 248 photos, about one a second | `docs/validation.md`, Test 7c: 248 of 248 placed, 1.02 s per photo. |
| Rough map ready in about 5 min | Test 7c: 254.1 s to place the photos plus 37.1 s to draw the picture = 291 s. |
| Detailed map takes 80 min | `docs/validation.md`, middle tier run: 80.2 min. |
| Rough map is off by about 12 m | Test 7c: median 11.8 m from the middle-tier map (90% within 19.0 m, worst 42.0 m). |
| ±1.1 m, 326 surveyed ground points, no survey markers | `docs/validation.md`, Vertical: spread 1.09 m against 326 RTK ground points after removing the constant offset. Absolute heights are about 43 m off, which is why the screen says "height differences". |

## Must be true before submitting
| Line | Today (17 Nov) |
|---|---|
| "The map grows while the drone is still in the air." | Measured only by replaying recorded photos in order. Not tested on a live feed from a drone, and it failed on our own August night video (Test 7d). |
| "Rescue teams start reading the ground before the drone lands." | Follows from the line above; same condition. |
| "Enough to size a debris pile" | Our stated use of the ±1.1 m figure. No debris pile has been measured against a tape yet. |
| Clear first, fly next | **Not built.** Planned as F4 for the finale. The scene is labelled an illustration. |
| "One laptop, no internet" (title card) | True for the current app. |

If a line is not true on the day, cut that scene or change the words. Each scene is separate in the file, so one can be removed and the rest re-rendered.

## Slots for the lead
- **Voiceover:** the 14 on-screen sentences total about 135 words, which is too fast to read aloud in 45 seconds (about 3 words a second). The voiceover should say less than the screen shows: one spoken sentence per scene is enough.
- **Team clip:** best placed after the logo, or between scenes 3 and 4. It would take the total past 45 seconds.
- **Our own flight footage (17 Nov):** best behind scene 2 or scene 6, in place of the drawn background.
