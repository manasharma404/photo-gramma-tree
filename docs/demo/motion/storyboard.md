# Fallback video: storyboard (45 seconds)

**Status: draft, 17 Nov. The lead approves the wording.** This video is a fallback for the finale. It is only submitted if every line in "Must be true before submitting" is true on the day.

- Scene file: `docs/demo/motion/fallback.html`. Render: from `web/`, `MOTION_SCENE=fallback.html node scripts/motion_render.mjs ../docs/demo/motion/out/typhon_fallback_45s.mp4` (about 30 minutes).
- Quick look at single frames: `bash docs/demo/motion/check_stills.sh fallback.html 4.9,20.5,33.2`.
- No sound. Voiceover, music, the team clip and our own flight footage are added by the lead.

## The story in one line
Nepal, 26 August 2026: a valley's roads and bridges are cut → nobody knows which roads still hold → Typhon → what we measured and what it buys → the two decisions → back to the road → logo.

The case study was Kedarnath in the first draft. The lead changed it to Nepal on 17 Nov.

## Scene by scene
| Time | Scene | Words on screen | Picture |
|---|---|---|---|
| 0.0–6.0 | 1. The case | "26 August 2026. A glacier collapse and a landslide send a flash flood into Nepal." / "About 40 km of road damaged. Roads were passable only as far as Nuwakot." / counter to 41, "Bridges destroyed or damaged" | A road draws across, debris falls on it, then more breaks appear along it. A drawing, not a map of the place. No death toll on screen. |
| 6.0–11.5 | 2. The problem | "The UN said the biggest obstacle to the response was access." / "Which roads still hold? Unknown." | Rows of outlined UNKNOWN drifting. A lime line opens into the title. |
| 11.5–15.0 | 3. Title | "TYPHON." / "The first map after a landslide, from one small drone." | Sand title card. |
| 15.0–20.9 | 4a. Speed | "The map grows while the drone is still in the air." / 248 photos placed, about one a second / rough map ready in about 5 min / detailed map takes 80 min / rough map is off by about 12 m / **"Rescue teams start reading the ground before the drone lands."** | Our real South Fork surface model rising; the real flight path. |
| 20.9–26.0 | 4b. No ground crew | "Height differences come out right to about one metre." / ±1.1 m against 326 surveyed ground points / survey markers placed: none / enough to size a debris pile / **"Nobody walks onto the slide before the map exists."** | Same model, camera still turning. |
| 26.0–37.5 | 5. The decision | "Typhon turns the map into a graph of roads and villages, then answers two questions." / "Question 1 · Clear first: which blocked road, once cleared, reconnects the most people?" / "Question 2 · Fly next: which unknown road is worth the next flight?" | A small road graph: open, blocked, unknown. The blocked road lights up and three villages reconnect; then a drone flies the unknown road. Labelled as an illustration. |
| 37.5–41.0 | 6. The close | "When the next road is cut, the first map should take minutes." | The cut road again; a drone flies along it. |
| 41.0–45.0 | 7. Logo | Typhon logo / "The first map after the landslide." / "Team Vortex · hackFront India 2026 · Problem statement T8.2" | Sand card with the lead's logo (`web/src/assets/logo-lockup.svg`). |

Labels that stay on screen: scene 1 "Sources: Nepal Department of Roads via Kathmandu Post, 29 Aug 2026 · UN News, 31 Aug 2026"; scene 2 "Source: UN News, 31 August 2026"; scene 4 "Measured on a replay of a USGS survey flight · not our footage"; scene 5 "Illustration of the method · not a screen from the app".

## Where each number comes from
| On screen | Source |
|---|---|
| 26 August 2026, glacier collapse and landslide, flash flood | UN News, 31 Aug 2026: https://news.un.org/en/story/2026/08/1168233 . The article says the flood was "triggered by a glacier collapse and landslide on Nepal's border with China on Wednesday" (26 Aug). Page text read in full on 17 Nov 2026. |
| "Roads were passable only as far as Nuwakot" / "the biggest obstacle to the response was access" | Same UN News article: "Access remains the single biggest obstacle to the response, according to the UN emergency relief agency, OCHA. Roads are passable only as far as Nuwakot". On screen it is a paraphrase in the past tense, without quotation marks. |
| About 40 km of road damaged, 41 bridges destroyed or damaged | Kathmandu Post, 29 Aug 2026, citing Nepal's Department of Roads (road between Rasuwagadhi and Malekhu): https://kathmandupost.com/national/2026/08/29/washed-out-bridges-force-flood-hit-communities-to-rely-on-choppers . Page text read on 17 Nov 2026. |
| Not shown: deaths | The UN gave 903 confirmed dead and more than 4,200 missing on 31 Aug 2026. Later counts are higher and not verified by us. If the voiceover mentions a toll, give the figure with its date. |
| 248 photos, about one a second | `docs/validation.md`, Test 7c: 248 of 248 placed, 1.02 s per photo. |
| Rough map ready in about 5 min | Test 7c: 254.1 s to place the photos plus 37.1 s to draw the picture = 291 s. |
| Detailed map takes 80 min | `docs/validation.md`, middle tier run: 80.2 min. |
| Rough map is off by about 12 m | Test 7c: median 11.8 m from the middle-tier map (90% within 19.0 m, worst 42.0 m). |
| ±1.1 m, 326 surveyed ground points, no survey markers | `docs/validation.md`, Vertical: spread 1.09 m against 326 RTK ground points after removing the constant offset. Absolute heights are about 43 m off, which is why the screen says "height differences". |

## Must be true before submitting
| Line | Today (17 Nov) |
|---|---|
| The Nepal figures in scenes 1 and 2 | True as reported on 29 and 31 Aug 2026. They are early figures: check before the finale whether the Department of Roads has published a final count. |
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
