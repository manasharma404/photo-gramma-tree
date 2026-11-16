# Test flight checklist (17 Nov, morning)

One flight has to give us two things: a test of the growing map on our own footage, and clips for the demo video. Read this on your phone at the field.

## Why the last flight could not be used
The August clip was shot at night with the camera looking across the field. The growing map needs to look straight down (validation Test 7d).

## Part A: the mapping pass (this is the test)
1. **Daylight**, not dusk. Avoid long shadows if you can: mid-morning is fine.
2. **Camera straight down.** Tilt the gimbal to its lowest stop (DJI lists the Neo 2's tilt range as -90° to 70°; -90° is straight down). Check on the phone screen that you see no horizon at all.
3. **One steady height** for the whole pass. Start at about 30 m if that is allowed where you fly; write down the height you used.
4. **Fly slowly**, about walking-to-jogging pace. Fast flight blurs the frames.
5. **At least three parallel lines, four if the battery allows.** Space the lines about one flying-height apart (30 m up, lines about 30 m apart). This spacing is a rule of thumb, not yet checked for the Neo 2's lens: the footage will tell us.
6. **Record one continuous 4K video** for the whole pass, turns included. Do not stop and restart between lines.
7. **Pick ground with detail:** paths, markings, parked things, edges. Plain grass alone gives the software nothing to match. Avoid people moving through the frame where you can.
8. **Never one straight line only** (our 34 m lesson from Run 1).

## Part B: things we can measure (10 minutes, before take-off)
1. Put down **4 to 6 markers** the camera can see from above: A4 sheets with a thick black X, weighted down, or bright cloth. Spread them across the area, not in a row.
2. **Tape-measure the distance between at least three pairs** of markers. Write each one down with the pair's names (for example A–B 18.40 m).
3. Photograph the notes. These numbers fill the "Tool vs tape" section of `docs/validation.md`, which is still PENDING.

## Part C: clips for the video (after the mapping pass)
- Take-off from the hand or the ground, from the side.
- The drone overhead against the sky, five seconds.
- A slow rise straight up with the camera pointing down (a good opening shot).
- You and your teammate with the controller and the laptop. This part is yours to direct.

## Getting the files to the laptop
- **Copy the original video files** from the drone by cable or card. **Do not send them through WhatsApp or any app that shrinks video:** our software reads the GPS track stored inside the original file, and re-encoding removes it.
- Tell Claude the file names, the flying height, and the tape measurements.

## What comes back
Claude runs the growing-map test on the mapping pass and reports works or fails, with numbers. That result decides whether a campus flight is part of the finale demo.

## Before you fly
Check that flying is allowed at that spot and height. This checklist does not cover permissions.
