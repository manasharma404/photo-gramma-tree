# Project Typhon · finale deck · speaker notes

The honest details behind each slide. Every number comes from a run file or report named here; simulated parts are said out loud.

## 1. Rapid drone mappingfor disaster relief.

Open with the job, not the tech: responders need a current map and a decision in the first hours. Typhon turns one consumer drone flight into that on a laptop, offline. The picture is our artwork, not a map.

## 2. A landslide closes a valley. Every map you have is from before.

Mentors asked "why not Google?" in round 1. Answer here: those maps are from before the slide. Keep it to 20 seconds.

## 3. From one flight to the relief plan.

One input, one processor, three answers. Field reports from phones go back into the graph, so the plan updates when the ground changes. Everything runs on the laptop; phones join its hotspot.

## 4. 

±6.06 m is the 4 Nov middle-tier run (data/runs/2026-11-04_2243.../accuracy.json). The map page's box shows ±6.09 m from the 31 Oct quick run; both are real. 34.2 m to 6.1 m: docs/validation.md, Run 1 vs Run 2. Say the sample size out loud.

## 5. Heights: trust the ground nearby.

Mean offset +43.49 m; spread 1.09 m std after removing the constant offset. This is why every measurement is made against nearby ground.

## 6. 13.14 ha in 80.2 min on one laptop.

Run files under data/runs/. The growing map's 1.2 s typical (1.5 s worst) was on an idle laptop; this morning, with Neo4j and a browser busy, one replay showed 7.0 s per photo: say "about a second when the laptop isn't busy". The rough map is 10 to 20 m: for seeing, not measuring. In the demo the photos are replayed from disk.

## 7. Opens in the tools they already use.

Exports were opened in QGIS and Google Earth by the teammate on 31 Oct (verification screenshots in the repo). Offline check run this morning on the merged code: 128 requests, 0 to the internet.

## 8. Who can get through, per vehicle.

Say "simulated" before anything else: our own drone data has no landslide with broken roads, so the demo lays simulated damage and people on the real road network of the 2024 Wayanad area. No made-up counts sit on real villages. Counts from the advisor (NetworkX and Neo4j agree).

## 9. Each blockage lets a different vehicle through.

The same road network gives four different answers because each vehicle has different limits (vehicle limits are PLACEHOLDER values in config/vehicles.yaml until sourced).

## 10. Two engines, one answer.

Measured this morning on this laptop: Neo4j confirmations took 11.5 to 23 s on the 1,568-road demo network depending on load (50 s once while two app copies used it). The dashboard never waits for it: NetworkX answers first, Neo4j checks and the panel says whether they agree. Plain-Cypher and GDS results match NetworkX in the tests.

## 11. A field report redraws the plan.

94 → 55 is the demo scenario's real computation (simulated counts). The 3 s report loop was tested end to end on 21 Nov (web/scripts/report_loop_test.mjs).

## 12. Blurred photos? Fly it again.

The plan is an estimate from the settings shown. The blurred patch is part of the simulated scenario.

## 13. What we have, and what we don't.

Debris model: recall 0.27, precision 0.64 on the held-out CAS region; on 35 South Fork road crops recall 0.04 (1 true positive). That is why it never marks a road blocked on its own.

## 14. A service first, then a product.

Software is open source with no per-map cloud bill. The cost line is an estimate from listings checked on 21 Nov.
