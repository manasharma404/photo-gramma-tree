# Finale runbook (Sat 21 – Sun 22 Nov, IIIT Delhi)

**Status: DRAFT, 19 Nov.** The parts for features built at the finale say `PENDING` until the lead's finale plan (Fri 20) names them. Everything else uses commands that exist today. Rehearse it on Friday; **the runbook passes when it is run twice end to end without help.**

Setup detail lives in: `README.md` ("Run it"), `docs/runbook_advisor.md` (Neo4j and the advisor), `docs/phone_check.md` (phone on the hotspot).

## 1. Friday night (before leaving)
| # | Do | Check | Who |
|---|---|---|---|
| 1 | `git pull`; push the baseline; clone it fresh into a temp folder; `uv sync`; `uv run pytest -q`; `cd web && npm install && npm run build` | Fresh clone builds; tests pass. **21 Nov, commit `a0e2595`: `uv sync` OK, 106 passed / 2 skipped, web build OK** (repeat after the last pre-event push) | Claude |
| 2 | Docker Desktop starts; ODM image already pulled; Neo4j image already pulled (`docs/runbook_advisor.md` step 1.3) | `docker images` lists both; nothing needs downloading at the venue | Lead |
| 3 | Data on the laptop: South Fork project, Nepal pack, the 50 test crops, the pre-event terrain, model weights (if trained). **Nepal terrain: done 21 Nov** (`uv run python scripts/prefetch_nepal_terrain.py --offline` rebuilds it). **Nepal roads: not on this laptop yet:** run `uv run python scripts/prefetch_nepal.py` once while online | Each opens with Wi-Fi off | Claude + teammate |
| 4 | Offline check: `cd web && node scripts/offline_check.mjs` | "0 requests left the laptop" | Claude |
| 5 | Copies of the fallbacks on a USB stick and on the phone: `docs/demo/motion/out/typhon_fallback_45s_v2.mp4`, the deck, a screen recording of the full demo | Each plays without the laptop | Lead |
| 6 | Chargers, extension board, USB-C hub, the phone that makes the hotspot, drone batteries charged, markers and tape (if a campus flight is allowed) | Packed | Lead |

## 2. Arrival (Sat 14:00–15:00)
1. Laptop on charge. Wi-Fi off unless the step needs it.
2. Start Docker Desktop; wait until `docker info` answers.
3. Neo4j: collect the AuraDB access at the partner desk (from 14:30). Put it in the local `.env` only, never in chat or in the repo. If AuraDB is not ready, use the local container (`docs/runbook_advisor.md`) and keep going.
4. Start the app: `uv run python -m api.main` (sign-in is on). In your own terminal, show the access codes with `uv run python -m auth.codes`: one operator code (you), one evaluator code (judges, on a card at the table), one PIN per field team. Never paste them in a chat. Sign in at `/login`.
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
| Growing map falls behind the replay (seconds per photo above 1.0) | The whole-map re-solve grows with the map (Test 7e: 24 s at 298 frames) | Switch to the USGS replay, which kept pace in Test 7c (1.02 s); say the number on screen out loud; never speed up the clock |
| Our own flight's map has no scale or north | `REC_0028` carries no GPS (Test 7e) | Say so; it is shown in map units. Never quote metres from it |
| Debris model too slow or wrong on stage | GPU busy or a bad crop | Show the stored result for that road with its timestamp, and say it is stored |
| Laptop dies or nothing runs | — | Fallback video plus deck from the USB stick; say plainly that the live build failed |

## 6. Rules on the day
- **No new features after 09:00 Sunday** (guide); our code freeze is 08:00.
- If a fix lands too late to test, it does not ship.
- Every demo action is run end to end before each round, not just before the jury.
- Push only after `git pull`; never force-push.

## 6b. ArgosX security scans (gate: baseline by 23:59 Sat, final by 11:00 Sun)
1. App running with sign-in on (`uv run python -m api.main`).
2. `powershell -ExecutionPolicy Bypass -File scripts\argosx_tunnel.ps1`: it prints a temporary `https://…trycloudflare.com` link (tested 21 Nov: the app answered, every private page asked for sign-in, wrong codes were refused, and the link went dead on closing).
3. Paste the link into ArgosX, run the scan, **download the report** (`docs/security/argosx_baseline.pdf`, later `argosx_final.pdf`).
4. Press Enter in the script window: the tunnel closes.
5. Fix critical and high first; keep a remediation log: found / fixed / remaining and why.

## 7. Submission (Sun, by 11:30; the portal locks at 12:00)
1. Final `git pull`, then push `main`. The repository link is the main submission.
2. **Only if the portal asks for a zip:** `uv run python scripts/make_submission_zip.py`. It writes `typhon_submission_<commit>.zip` next to the repo folder, and refuses if you are not on `main`, have uncommitted changes, or `main` differs from GitHub, so the zip always matches GitHub. Never upload a zip made from someone's own folder.
3. Demo video and deck (PDF export) as in `PLAN.md` ("The pitch deck").
4. Post in the team chat what was submitted and when.
