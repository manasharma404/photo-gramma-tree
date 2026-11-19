# Finale runbook (Sat 21 – Sun 22 Nov, IIIT Delhi)

**Status: DRAFT, 19 Nov.** The parts for features built at the finale say `PENDING` until the lead's finale plan (Fri 20) names them. Everything else uses commands that exist today. Rehearse it on Friday; **the runbook passes when it is run twice end to end without help.**

Setup detail lives in: `README.md` ("Run it"), `docs/runbook_advisor.md` (Neo4j and the advisor), `docs/phone_check.md` (phone on the hotspot).

## 1. Friday night (before leaving)
| # | Do | Check | Who |
|---|---|---|---|
| 1 | `git pull`; push the baseline; clone it fresh into a temp folder; `uv sync`; `uv run pytest -q`; `cd web && npm install && npm run build` | Fresh clone builds; tests pass (record the line here: PENDING) | Claude |
| 2 | Docker Desktop starts; ODM image already pulled; Neo4j image already pulled (`docs/runbook_advisor.md` step 1.3) | `docker images` lists both; nothing needs downloading at the venue | Lead |
| 3 | Data on the laptop: South Fork project, Nepal pack (once it is real OpenStreetMap), the 50 test crops, the pre-event terrain, model weights (if trained) | Each opens with Wi-Fi off | Claude + teammate |
| 4 | Offline check: `cd web && node scripts/offline_check.mjs` | "0 requests left the laptop" | Claude |
| 5 | Copies of the fallbacks on a USB stick and on the phone: `docs/demo/motion/out/typhon_fallback_45s_v2.mp4`, the deck, a screen recording of the full demo | Each plays without the laptop | Lead |
| 6 | Chargers, extension board, USB-C hub, the phone that makes the hotspot, drone batteries charged, markers and tape (if a campus flight is allowed) | Packed | Lead |

## 2. Arrival (Sat 14:00–15:00)
1. Laptop on charge. Wi-Fi off unless the step needs it.
2. Start Docker Desktop; wait until `docker info` answers.
3. Neo4j: collect the AuraDB access at the partner desk (from 14:30). Put it in the local `.env` only, never in chat or in the repo. If AuraDB is not ready, use the local container (`docs/runbook_advisor.md`) and keep going.
4. Start the app: `uv run python -m api.main`. Note the field PIN it prints.
5. Open `http://localhost:8000`; check the map, the 3D view and one road panel.
6. Phone: hotspot on with **mobile data off**; laptop joins it; `uv run python scripts/qr.py`; phone opens `/field` (`docs/phone_check.md` steps 1–4).
7. Post the time and "baseline runs" in the team chat.

## 3. Demo start order (every time, also before each round)
| # | Step | Ready when |
|---|---|---|
| 1 | Docker running | `docker info` answers |
| 2 | Neo4j reachable (AuraDB or local) | advisor check in `docs/runbook_advisor.md` prints a result |
| 3 | `uv run python -m api.main` | page loads at `http://localhost:8000` |
| 4 | Phone on the hotspot, `/field` open, PIN entered | test report reaches the dashboard in about 3 s |
| 5 | Growing map, staged and paused at photo 0 (F1) | PENDING (finale build) |
| 6 | Reset to the starting state | PENDING: a "reset demo" action is planned (Mentor Round 2 notes in `PLAN.md`); it does not exist yet |

## 4. Demo script
Timings come from `PLAN.md` ("How we are scored"). The jury slot is six minutes including the demo.

| Time | Say | Show | Status |
|---|---|---|---|
| 0:00–0:40 | The problem and the user: Nepal, 26 Aug 2026; 41 bridges; access was the biggest obstacle (sources in `docs/demo/motion/storyboard.md`) | Start the growing map in the first ten seconds so it fills while we talk | Map replay: PENDING (F1) |
| 0:40–3:40 | The loop live: see, suspect, decide, fly again | Growing map → debris on roads → clear first / fly next | PENDING (F1–F4, lead's plan Fri) |
| 3:40–4:30 | A judge taps a road | Road panel: status, evidence, trust level | Road panel exists today; evidence from the model: PENDING (F3) |
| 4:30–5:15 | What is underneath, what we built in 22 hours | Commit list since 14:00 Sat | Ready on the day |
| 5:15–6:00 | First adopter, who pays, next milestone | One slide | Deck: PENDING |

**Numbers we may say** are only those in `docs/validation.md` and the storyboard's source table. Anything not run says PENDING out loud ("not measured yet").

## 5. If this breaks
| Symptom | Likely cause | Fix (in this order) |
|---|---|---|
| Page does not load on the laptop | App not running, or port taken | Restart `uv run python -m api.main`; check the terminal for the error |
| Phone cannot load anything | Firewall, or laptop on another network | `docs/phone_check.md` "If this breaks" |
| Map is blank | Tiles not built for the active project | Switch to South Fork (`data/active.json`); rebuild tiles later |
| Neo4j query fails with "unknown procedure" | AuraDB without the graph plugin | Use the plain Cypher queries (teammate report, T3) or the NetworkX fallback; say which one is running |
| AuraDB unreachable | Venue network | Local Neo4j container; if that fails too, NetworkX fallback |
| Docker will not start | WSL or Docker Desktop stuck | Restart Docker Desktop once; if still stuck, demo from the existing South Fork outputs (no new processing) |
| Growing map stalls or drifts | Photos not looking straight down, or too little overlap | Switch to the USGS replay; never fake progress | 
| Debris model too slow or wrong on stage | GPU busy or a bad crop | Show the stored result for that road with its timestamp, and say it is stored |
| Laptop dies or nothing runs | — | Fallback video plus deck from the USB stick; say plainly that the live build failed |

## 6. Rules on the day
- **No new features after 09:00 Sunday** (guide); our code freeze is 08:00.
- If a fix lands too late to test, it does not ship.
- Every demo action is run end to end before each round, not just before the jury.
- Push only after `git pull`; never force-push.
