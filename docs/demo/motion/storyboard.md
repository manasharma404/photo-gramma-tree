# Fallback video: storyboard (45 seconds)

**Status: draft 3, 17 Nov. The lead approves the wording and the look.** This video is a fallback for the finale. It is only submitted if every line in "Must be true before submitting" is true on the day.

- Scene file: `docs/demo/motion/fallback.html`. Render: from `web/`, `MOTION_SCENE=fallback.html node scripts/motion_render.mjs ../docs/demo/motion/out/typhon_fallback_45s_v2.mp4` (about 30 minutes).
- Quick look at single frames: `bash docs/demo/motion/check_stills.sh fallback.html 5.6,18.5,33.6`.
- No sound. Voiceover, music, the team clip and our own flight footage are added by the lead.

## The story in one line
Nepal, 26 August 2026: a valley's roads and bridges are cut → nobody knows which roads still hold → Typhon → three things that set it apart, each with what it buys → the work behind it → the two decisions → logo.

History: the case study was Kedarnath in draft 1; the lead changed it to Nepal on 17 Nov. Draft 3 (same day) answers two notes from the lead: the plain scenes were redesigned, and small text was removed.

## Type rules (for a panel watching a laptop)
- Nothing on screen is smaller than 28 px at 1920 × 1080. Sentences are 72 px, big numbers 130 px and up, supporting lines 42 to 46 px, labels and source notes 28 to 30 px.
- One idea per screen. The corner clutter (project name, coordinates, timecode) is gone; the only standing small line is the source or disclosure note.
- These rules follow general guidance read on 17 Nov (size type for the screen it is watched on, few words per screen, plan for about two to three words a second). That guidance comes from motion-design blogs, not from a standard, and the reference videos were read about, not watched.

## Scene by scene
| Time | Scene | Words on screen | Picture |
|---|---|---|---|
| 0.0–6.0 | 1. The case | "26.08.2026" / "A glacier collapse and a landslide flood Nepal." / "41" bridges destroyed or damaged / "40 km" road damaged, about | A lime line bends into a road; debris lands on it with a shake and a flash; more breaks appear; 41 bars are knocked over one by one as the count runs. A drawing, not a map. No death toll on screen. |
| 6.0–10.5 | 2. The problem | "The UN called access the biggest obstacle." / "Which roads still hold?" / "UNKNOWN" | A wall of outlined UNKNOWN; one word snaps to lime. A lime line opens into the title. |
| 10.5–13.2 | 3. Title | "TYPHON." / "The first map after a landslide, from one small drone." | Sand title card. |
| 13.2–19.7 | 4a. Sets us apart 01 | "The map grows while the drone is still in the air." / "Rough map: about 5 min" / "Detailed map: 80 min" / **"Rescue teams start reading the ground before the drone lands."** | Our real South Fork surface model rising, the real flight path, and two bars drawn to the same scale (5 against 80). |
| 19.7–24.9 | 4b. Sets us apart 02 | "Height differences come out right to about one metre." / "±1.1 m", checked against 326 surveyed ground points / **"Nobody walks onto the slide before the map exists."** | Same model, camera still turning. |
| 24.9–29.3 | 5. The work behind it | "NO INTERNET. NO SURVEY CREW. ONE LAPTOP." / "Tested on real flights. The failures are published too." | A sand card drops over the terrain, three lines of large type. |
| 29.3–38.6 | 6. Sets us apart 03 | "It doesn't stop at the map. It answers two questions." / "Question 1, clear first: which blocked road, once cleared, reconnects the most people?" / "Question 2, fly next: which unknown road is worth the next flight?" | A small road network in 3D blocks: the debris on one road is cleared, a light runs along it and three villages turn lime; then a drone flies the unknown road. Labelled as an illustration. |
| 38.6–41.6 | 7. The close | "Next time, the first map should take minutes." | A lime line sweeps the wall and every UNKNOWN becomes KNOWN. |
| 41.6–45.0 | 8. Logo | Typhon logo / "The first map after the landslide." / "Team Vortex · hackFront India 2026 · Problem statement T8.2" | Sand card with the lead's logo (`web/src/assets/logo-lockup.svg`). |

Notes that stay on screen: scene 1 "A drawing, not a map. Sources: Nepal Department of Roads; UN News. August 2026."; scene 2 "Source: UN News, 31 August 2026."; scene 4 "South Fork, California. Replay of a USGS survey flight, not our footage. Rough map is off by about 12 m."; scene 6 "An illustration of the method, not a screen from the app."

## Where each number comes from
| On screen | Source |
|---|---|
| 26 August 2026, glacier collapse and landslide, flood | UN News, 31 Aug 2026: https://news.un.org/en/story/2026/08/1168233 . The article says the flash flooding was "triggered by a glacier collapse and landslide on Nepal's border with China on Wednesday" (26 Aug). Page text read in full on 17 Nov 2026. |
| "The UN called access the biggest obstacle" | Same article: "Access remains the single biggest obstacle to the response, according to the UN emergency relief agency, OCHA." On screen it is a paraphrase, without quotation marks. |
| 41 bridges destroyed or damaged, about 40 km of road damaged | Kathmandu Post, 29 Aug 2026, citing Nepal's Department of Roads (road between Rasuwagadhi and Malekhu): https://kathmandupost.com/national/2026/08/29/washed-out-bridges-force-flood-hit-communities-to-rely-on-choppers . Page text read on 17 Nov 2026. |
| Not shown: deaths | The UN gave 903 confirmed dead and more than 4,200 missing on 31 Aug 2026. Later counts are higher and not verified by us. If the voiceover mentions a toll, give the figure with its date. |
| Rough map: about 5 min | `docs/validation.md`, Test 7c: 254.1 s to place 248 photos plus 37.1 s to draw the picture = 291 s. |
| Detailed map: 80 min | `docs/validation.md`, middle tier run: 80.2 min. |
| Rough map is off by about 12 m (in the note) | Test 7c: median 11.8 m from the middle-tier map (90% within 19.0 m, worst 42.0 m). |
| ±1.1 m, 326 surveyed ground points | `docs/validation.md`, Vertical: spread 1.09 m against 326 RTK ground points after removing the constant offset. Absolute heights are about 43 m off, which is why the screen says "height differences". |
| "Tested on real flights. The failures are published too." | `docs/validation.md` in the public repo: Runs 1 to 6 and Test 7, on USGS survey flights and our own Neo 2 video, including the tests that failed (7a, 7d) and the one judged a no-go (7b). |

## Must be true before submitting
| Line | Today (17 Nov) |
|---|---|
| The Nepal figures in scenes 1 and 2 | True as reported on 29 and 31 Aug 2026. They are early figures: check before the finale whether the Department of Roads has published a final count. |
| "The map grows while the drone is still in the air." | Measured only by replaying recorded photos in order. Not tested on a live feed from a drone, and it failed on our own August night video (Test 7d). |
| "Rescue teams start reading the ground before the drone lands." | Follows from the line above; same condition. |
| "No internet. One laptop." | True for the current app. The growing map and the two decisions, built at the finale, must also run with Wi-Fi off. |
| "No survey crew." | True: no run has used ground control. Surveyed points were used only to check the result. |
| Clear first, fly next | **Not built.** Planned as F4 for the finale. The scene is labelled an illustration. |

If a line is not true on the day, cut that scene or change the words. Each scene is separate in the file, so one can be removed and the rest re-rendered.

## Slots for the lead
- **Voiceover:** the screen carries about 150 words including labels, which is more than a voice can read in 45 seconds. The voiceover should say less than the screen shows: one spoken sentence per scene is enough.
- **Team clip:** best placed after the logo, or between scenes 3 and 4. It would take the total past 45 seconds.
- **Our own flight footage (17 Nov):** best behind scene 2 or scene 7, in place of the type wall.
