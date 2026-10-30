# TEAMMATE.md: what the teammate delivers

**Status: APPROVED by the lead, 31 Oct 00:30 IST.** Once approved, Claude turns this into one self-contained prompt for the teammate's agent.

**Folders she may change:** `advisor/`, `ml/`, plus `neo4j/` (compose file). **Not allowed:** anything else; `contracts/` changes only through the lead and the `PLAN.md` decisions log.

**Hard rules:** no invented numbers (missing = `PLACEHOLDER`, mocks carry `"mock": true`); no internet at runtime; ask before pushing; never force-push; if something is impossible, stop and tell the lead.

## Route advisor (`advisor/`), must have
| # | Deliverable | Done when | Target (IST) |
|---|---|---|---|
| A1 | Neo4j via `neo4j/docker-compose.yml`, image tag pinned, GDS plugin downloaded once online | Restart with Wi-Fi off still prints `gds.version()` | 10:00 |
| A2 | Loader: builds the graph from our `segments.geojson` + `places.geojson` (landing zones come in as facilities) | Works on the mock files today; on South Fork files when we hand them over (~16:00) | 12:00 |
| A3 | Routing per vehicle type (truck / jeep / foot): who is reachable, who is cut off, reopen plan ranked by people reconnected → `access_report.json` | Matches the contract; NetworkX fallback gives the same JSON in a test | 14:00 |
| A4 | FastAPI `APIRouter` in `advisor/` with `GET /advisor/state` (shape in `PLAN.md`) and field dead-end reports (POST) | Lead mounts it with one `include_router` line and it runs | 15:00 |
| A5 | Phone page served at `/field`: defaults to "tap where you are" (no https needed); report a dead end | Opens on a phone over the hotspot | 16:00 |
| A6 | Wayanad scenario: OSM roads, road states from cited reports, labelled "scenario reconstructed from reports, not drone-measured"; sources listed | Runs on its own, independent of our data | 16:00 |

## ML (`ml/`)
| # | Deliverable | Done when | Target (IST) |
|---|---|---|---|
| M1 | **Image-quality model** that scores photos / video frames → `image_quality.json` (contract in `PLAN.md`), with a predict CLI: `python -m ml.quality --in <folder or mp4> --out image_quality.json` | Runs offline on the Neo 2 clips; model name, version, licence and what it was trained/tested on are written down | 16:00 |
| M2 | (Optional) road-status scores → `ml_scores.json` per `segment_id` | Only if M1 is done | 16:00 |

**Integration note:** until M1 lands, `pipeline/` uses a standard brightness + sharpness check. When M1 lands, the pipeline reads `image_quality.json` instead, and the UI names it by its real model, never a vague "AI".

## Should, if time
- `population` for places, with a cited source (else `PLACEHOLDER`)
- Situation-report translation (Sarvam Translate, GPL-3.0; licence logged)

## What she needs from us, and when
- Mock `segments.geojson`, `places.geojson` and the three new contract examples: **by 02:00**
- Real South Fork `segments.geojson` + `places.geojson` + landing zones: **by 16:00**
