# Fixes for video version 3 (5 Nov 2026, 01:10)

Paste everything below the line into Antigravity on the video laptop, together with `phone.mp4` and `dash.mp4`.

---

Version 3 (`VID-20261105-WA0003.mp4`) is a big improvement: the voiceover, the four number fixes, the 80-minute clock, 880 → 220 frames, 99 requests, and the new Fly / Map / Decide card text are all right. **Keep everything else as it is.** Make only these four fixes. Number 1 is required before upload.

**Hard rules (same as before):** no new numbers, no new claims, nothing on screen that the app does not actually show. If a fix is impossible, stop and tell the lead.

1. **(Required) Replace the fake dashboard in the report beat (about 0:53–1:05).**
   - **Problem:** the laptop screen labelled "LAPTOP DASHBOARD" is a QGIS screenshot of Wayanad roads. The "BLOCKED" stamp and the notice "FIELD REPORT RECEIVED (HOTSPOT) · Road seg_WAY_0011 marked BLOCKED · Priority recalculated in 3 s" are drawn on top; the app never showed them. A judge who opens the app will see something different, so this reads as a mock-up passed off as the product.
   - **Fix:** put the real recordings in the two frames.
     - Phone frame: `phone.mp4`, 0–9 s. The Submit tap is at about 6 s.
     - Laptop frame: `dash.mp4`, 12–19 s. The real notice appears at about 16 s, and the road turns red at the same moment.
     - Line the two up so the dashboard notice appears about 3 s after the phone tap.
     - Delete the drawn BLOCKED stamp and the drawn notice.
     - Keep the "SYNCED IN 3 S" chip and the mono line; both are true (`web/scripts/report_loop_test.mjs`).
     - Both clips show the South Fork map, so the phone frame no longer shows Wayanad.
   - **If `dash.mp4` cannot be used:** remove the laptop frame entirely and show only the phone clip with the caption. Do not show a mock-up.

2. **Fill the empty screen at 0:12.75–0:20.** For over 7 seconds the frame is blank paper with only the caption pill "A drone: already in the jeep." Keep v1's satellite-vs-drone split on screen for this whole stretch (or a slow zoom on the drone icon) until the logo wipe.

3. **Move the report-beat headline off the logo.** "Ground teams report by phone over the offline hotspot." overlaps the TYPHON logo at top left. Move it down about 40 px, or shorten it to "Field reports, over the hotspot."

4. **Smaller ones (do them if there is time):**
   - The Neo 2 map card disappears about 2 s before the scene ends (around 1:13), leaving an empty frame. Keep the card on screen until the cut.
   - Right after the report beat, the old v1 phone shot ("Field teams report from a phone on the laptop's hotspot") repeats the same idea. Cut it and give the time to the report beat.

**Check before sending:**
- Re-export at 1920x1080, 90.0 s or less.
- Keep the voiceover level as it is now (it measures −16.7 LUFS, which is right).
- Send frame grabs at 0:15, 0:58, 1:02 and 1:12.
- Finish by **03:30 IST**. If only fix 1 is possible, send that.
