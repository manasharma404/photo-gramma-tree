# Finale Build Plan: Project Typhon (team Vortex), PS T8.2

**Product:** one consumer drone and one laptop with no internet → a current map, which roads each vehicle can use, which blockage to clear first and which road to fly next. Starting point: git tag `finale-start` (commit `cc8f079`, 21 Nov 13:04); everything after it is built at the finale.

**Updated 21 Nov, 20:15 IST.** Sections 2 and 3 are the plan as submitted at 16:00; the status columns show where each item stands now. Statuses come from commits on GitHub (`main`, and the teammate's branch `teammate`) and from the tests in `docs/validation.md`. Work on the `teammate` branch is quoted from her own report (`docs/teammate_finale_report.md` on that branch); it is **not merged into `main` and not yet checked by the lead**. Anything not yet run says PENDING.

## 1. Where we started (21 Nov, 14:00)
| Worked at the start (measured) | Mocked, hardcoded or missing at the start |
|---|---|
| Drone photos → map on the laptop, offline (OpenDroneMap): 13.14 ha in 80.2 min; **±6.1 m at 3 surveyed checkpoints, no ground control**; relative heights ±1.1 m against 326 surveyed points (USGS public survey, not our footage) | **Every road on the real map reads "unknown"**: the trained debris model (held-out IoU 0.24) is not wired in |
| Rough map that grows while the drone flies: tested offline, not in the app. Kept pace on the USGS replay (1.02 s per photo); on our own flight 1.51 s per photo, so it fell behind | Growing map not in the app; not live from a drone (replayed from disk) |
| Measurements: crossing span, debris volume, helicopter landing zones, working space; exports COG, KMZ, GeoPackage, GeoJSON, PDF | Vehicle limits, priority weights and some helicopter sizes are labelled PLACEHOLDER |
| Field teams report from a phone (PIN) and the laptop map updates in seconds (tested 21 Nov) | No login for the laptop dashboard; one shared field PIN |
| Neo4j: route graph and access report run locally | "Clear first" and "fly next" exist only as tested queries, not in the product |

## 2. Where we will be by 12 PM, 22 Nov, and where we are at 20:15

**Update 06:30, 22 Nov (local commits on `main`, not pushed yet):**
- **Teammate branch merged** (`f688c46`): human confirm/reject of model suspicions with road history; Neo4j answers in plain Cypher; Clear First and Fly Next on the field page (items 2, 3; item 5 shifted to the teammate's iPad flow on `/field`). Full suite after the merge: **142 passed, 3 skipped** (Wayanad scenario and `ml_scores.json` not on this laptop).
- **Neo4j speed fix** (`fee4974`): an index on junctions. South Fork access report **108 s → 4–6 s**, still computed in Neo4j. **Nepal stays slow: about 90 s with Neo4j, 23 s with NetworkX** (106,000 junctions): not for live use.
- **Reset demo** (`03753bd`): `uv run python scripts/reset_demo.py`.
- **Offline check** on the merged code: 128 requests, **0 left the laptop**, 0 failed, 0 page errors.
- **Still open:** app restart (runs the old server code until restarted); push; the model scores and the iPad demo's scenario data onto this laptop; ArgosX baseline scan (PENDING) and the open tunnel; load test (not started); which timing to quote (145.6 vs 80.2 min).
| # | Promised for 12 PM | Status at 20:15 | Evidence |
|---|---|---|---|
| 1 | **The map grows while the drone flies, in the app:** each photo placed within about a second; drone GPS gives scale and north; "rough, not for measuring" on screen | **Done, in `main`** | Test 7f, commits `66b7858`, `3532189`. USGS block: 248 of 248 photos, on the map **1.2 s** after arriving (1.5 s worst), a median **11.8 m** off the measured map. Our flight: 297 of 298, **0.8 s** (1.1 s worst), drone positions a median **1.0 m** from the GPS track. Replayed from disk, not a live drone link |
| 2 | **Debris on roads:** the trained model scores all 498 South Fork roads; a suspicion shows as **"needs checking"** with its evidence image, never as "open" | **Built on the `teammate` branch; not merged** | Her report (commits `f8a2b6a`, `79df2bc`): all 498 roads scored in 1.53 s; the 16 roads inside the photos all score clear (they run through forest beside the slide); the other 482 stay unknown; one evidence image per road; a score of 0.15 or more raises "needs checking". **So on South Fork no road shows "needs checking"** |
| 3 | **The answer, computed in Neo4j:** per vehicle, route or "cut off"; **clear first**; **fly next** | **Queries built on the `teammate` branch; not yet on the map** | Her report: reach, clear first and fly next in plain Cypher (no plugin needed), matching NetworkX in her tests; fly next ranks a road higher when the model is unsure (a set rule in `config/priority.yaml`, not AI). Drawing it on the map: lead + Claude, after the merge |
| 4 | **Field team journey:** offline copy of the latest map; reports made out of signal wait on the phone and send on reconnect; a team confirms or rejects each model suspicion, with road history | **Saved map and outbox: done, in `main`. Confirm/reject and history: built on the `teammate` branch** | Commit `ea7420b`, checked in a browser: a report made offline was kept, then sent on reconnect marked with its observed time; the map PDF saved in 31 s. Limit: the phone page must stay open (no offline app over plain HTTP). Confirm/reject: her commit `79df2bc`, `GET /advisor/history` |
| 5 | **Judges' own input:** on an iPad, tap a road to block it or pick a vehicle; the plan redraws in seconds | **Not started** (lead + Claude); can start once item 3 is merged | — |
| 6 | **Access by role:** operator login on the laptop, a PIN per field team, a read-only view for evaluators | **Done, in `main`** | Commits `ce012ec`, `de4009b`; checked in a browser: no map without signing in, a wrong code refused, a team PIN opens only the field page, reports carry the team name. 11 automated tests also cover the lockout after 5 wrong codes and forged cookies |
| 7 | **Secured and measured:** two ArgosX scans with fixes between; a load test giving the number of devices one laptop serves | **Tunnel for the scans: done** and open now. Baseline scan: **PENDING (due 23:59)**. Final scan: due 11:00. Load test: **not started** | Commit `67cffb1`: through the public link only the sign-in page answers; data is refused without a code; the link dies when the tunnel closes |

*Stretch, only if 1–7 are done:* the slide outline and volume found automatically from before-and-after terrain (F2). **Not started.**

**Also needed before Round 2 (from the runbook):** a "reset demo" action (PENDING), and every demo action run end to end twice.

## 3. User segments
| Segment | Their problem | Status by 12 PM (plan) | At 20:15 |
|---|---|---|---|
| **Primary: district emergency operations centre (DDMA / DEOC officer)** | Which roads hold, what to clear first, where to look next, in the first hours | Working | Growing map and sign-in work in `main`; debris scores and the Neo4j answers are built on the `teammate` branch, waiting for the merge |
| **Field rescue teams (SDRF, NDRF, fire)** | Need the map out of signal; their ground truth must reach the plan | Working (feature 4) | Reports, team sign-in, outbox and saved map work in `main`; confirm/reject built on the `teammate` branch |
| Road owners (PWD, BRO) | Inventory of damaged roads; debris volume and gap span for machines and bridging | Partial (measurement tools exist) | Unchanged (built before the finale) |
| Insurers, mining operators | Fast, measured record of damage | Planned | Unchanged |

## 4. Partner technology: Neo4j, deepened
Today Neo4j holds the route graph. By 12 PM, **reach, clear first and fly next run as Cypher on Neo4j in the core flow** and are visible in the demo; NetworkX is the fallback and the screen says which one answered. Product need: these are path questions over a road network that changes with every field report, which is what a graph database is for. **At 20:15:** Neo4j runs on the demo laptop (ports bound to localhost); the three answers exist in plain Cypher on the `teammate` branch; they are not yet in `main` or on the map.

## 5. Rest of the night
| When | What | Who |
|---|---|---|
| **next** | **Merge the `teammate` branch into `main`:** review the diff against scope (15 files, about 2,000 lines); a dry-run merge at 20:15 found one conflict only, in `docs/AI_DISCLOSURE.md` (easy); her new endpoint (`GET /advisor/history`) and confirm/reject buttons fit the sign-in rules as they stand; then run the full tests and check it in the browser | Lead + Claude, teammate on hand |
| with the merge | Get the model's output onto the demo laptop: her `ml_scores.json` and evidence images live in `data/` (not in git), so either copy them over, or install ONNX Runtime and run her scoring here while online | Teammate + lead |
| by 23:59 | ArgosX **baseline scan**; save the report; start the remediation log | Lead (tunnel ready) |
| after the merge → 04:00 | Items 3 and 5: the Neo4j answers on the map; judges' input on the iPad | Lead + Claude |
| tonight, in a gap (proposed) | Load test (item 7); "reset demo" action | Lead + Claude |
| 04:00 → 07:00 | Join everything; run every demo action end to end; runbook passes twice | All |
| by 07:30 | Progress update on Discord | Pitch owner |
| **08:00** | **Code freeze.** Video and deck ready before 10:00 | All |
| by 11:00 | ArgosX **final scan**; remediation log complete | Lead + Claude |
| by 11:30 | Submit (portal locks at 12:00) | Pitch owner |

**Decision for the lead:** on South Fork, every photographed road scores clear, so the demo would show no "needs checking" there. Choose where the judges see a suspicion (for example the Nepal scenario, labelled "reconstructed from reports"), and never stage one on South Fork as if the model found it.

**If we slip:** item 5 shrinks to "pick a vehicle" only; F2 stays out. Items 1, 2 and 3 are the product and are not cut. A fix that lands after 08:00 does not ship.

## 6. Definition of done
A district team flies one drone and, before it lands, sees a rough map, which roads each vehicle can use, which blockage to clear first and where to fly next, with field teams confirming or correcting it from their phones: all on one laptop, with no internet. **At 20:15:** the rough map during the flight and the field reports work in `main`; the debris scores, confirm/reject and the three Neo4j answers are built on the `teammate` branch and must be merged, checked and drawn on the map.
