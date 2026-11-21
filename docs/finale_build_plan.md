# Finale Build Plan: Project Typhon (team Vortex), PS T8.2

**Product:** one consumer drone and one laptop with no internet → a current map, which roads each vehicle can use, which blockage to clear first and which road to fly next. Starting point: git tag `finale-start` (commit `cc8f079`, 21 Nov 13:04); everything after it is built at the finale.

## 1. Where we are (21 Nov, 14:00)
| Works today (measured) | Mocked, hardcoded or missing |
|---|---|
| Drone photos → map on the laptop, offline (OpenDroneMap): 13.14 ha in 80.2 min; **±6.1 m at 3 surveyed checkpoints, no ground control**; relative heights ±1.1 m against 326 surveyed points (USGS public survey, not our footage) | **Every road on the real map reads "unknown"**: the trained debris model (held-out IoU 0.24) is not wired in |
| Rough map that grows while the drone flies: tested offline, not in the app. Keeps pace on the USGS replay (1.02 s per photo); on our own flight 1.51 s per photo, so it falls behind | Growing map not in the app; not live from a drone (replayed from disk) |
| Measurements: crossing span, debris volume, helicopter landing zones, working space; exports COG, KMZ, GeoPackage, GeoJSON, PDF | Vehicle limits, priority weights and some helicopter sizes are labelled PLACEHOLDER |
| Field teams report from a phone (PIN) and the laptop map updates in seconds (tested 21 Nov) | No login for the laptop dashboard; one shared field PIN |
| Neo4j: route graph and access report run locally | "Clear first" and "fly next" exist only as tested queries, not in the product |

## 2. Where we will be by 12 PM, 22 Nov
1. **The map grows while the drone flies, in the app:** each photo placed within about a second, drone GPS gives scale and north (our flight: map within a median 1.4 m of the GPS track); "rough, not for measuring" shown on screen.
2. **Debris on roads:** the trained model scores all 498 South Fork roads; a suspicion shows as **"needs checking"** with its evidence image, never as "open".
3. **The answer, computed in Neo4j:** per vehicle, route or "cut off"; **clear first** (the blockage that reconnects the most people); **fly next** (the unchecked road that settles routes for the most people, ranked higher when the model is unsure).
4. **Field team journey (second segment):** before going out, a phone takes an offline copy of the latest map; reports made out of signal wait on the phone and send on reconnect; a team confirms or rejects each model suspicion, and the road keeps its history.
5. **Judges' own input:** on an iPad, tap a road to block it or pick a vehicle; the plan redraws in seconds.
6. **Access by role:** operator login on the laptop, a PIN per field team, a read-only view for evaluators.
7. **Secured and measured:** two ArgosX scans with fixes between; a load test giving the number of devices one laptop serves.

*Stretch, only if 1–7 are done:* the slide outline and volume found automatically from before-and-after terrain.

## 3. User segments
| Segment | Their problem | Status by 12 PM |
|---|---|---|
| **Primary: district emergency operations centre (DDMA / DEOC officer)** | Which roads hold, what to clear first, where to look next, in the first hours | Working |
| **Field rescue teams (SDRF, NDRF, fire)** | Need the map out of signal; their ground truth must reach the plan | Working (feature 4) |
| Road owners (PWD, BRO) | Inventory of damaged roads; debris volume and gap span for machines and bridging | Partial (measurement tools exist) |
| Insurers, mining operators | Fast, measured record of damage | Planned |

## 4. Partner technology: Neo4j, deepened
Today Neo4j holds the route graph. By 12 PM, **reach, clear first and fly next run as Cypher on Neo4j in the core flow** and are visible in the demo; NetworkX is the fallback and the screen says which one answered. Product need: these are path questions over a road network that changes with every field report, which is what a graph database is for.

## 5. Definition of done
A district team flies one drone and, before it lands, sees a rough map, which roads each vehicle can use, which blockage to clear first and where to fly next, with field teams confirming or correcting it from their phones: all on one laptop, with no internet.
