# AI disclosure

The hackFront rules require disclosure of AI-assisted work. One line per piece of work.

| Date | Tool | What it did | Reviewed by |
|---|---|---|---|
| 31 Oct 2026 | Claude Code (Claude Opus 5.5) | Drafted PLAN.md and TEAMMATE.md; machine and Docker checks; repo skeleton, .gitignore, contracts (JSON Schemas + mock examples) and their test | Lead |
| 31 Oct 2026 | Claude Code (Claude Opus 5.5) | Worked out the DJI Neo 2 telemetry layout from value ranges; wrote `pipeline/dji_telemetry.py`, `pipeline/frame_quality.py`, `pipeline/video_check.py` and tests | Lead |
| 31 Oct 2026 | Claude Code (Claude Opus 5.5) | Wrote `pipeline/subset.py`, `pipeline/run_odm.py`, `accuracy/find_targets.py`, `accuracy/compute_errors.py` and tests; ran ODM; analysed the single-strip accuracy failure; wrote `docs/validation.md`; reviewed and merged the teammate's branch; wrote her prompts (`docs/teammate_prompt.md`, `docs/teammate_followup_1.md`). Target IDs SF10/SF11 were confirmed visually by Claude and still need the lead's confirmation | Lead |
| 31 Oct 2026 | Claude Code (Claude Opus 5.5) | Wrote `pipeline/tiles.py`, `pipeline/terrain.py`, `pipeline/activate.py`, `pipeline/video_frames.py`, `accuracy/vertical.py`, `accuracy/router.py`, `measure/` (span, volume, working space, landing zones), `roads/segments.py` and their tests; ran the 5-line block (quick + full) and the Neo 2 run; wrote `scripts/prefetch_osm_southfork.py`, `scripts/make_samples.py`, `scripts/make_snapshot.py` | Lead |
| 31 Oct 2026 | Claude Code (Claude Opus 5.5) | Built the web UI (`web/`: landing page, dashboard, MapLibre map, three.js 3D view, tool panels) to the lead's layout and visual direction; rendered the landing hero callouts; headless-browser screenshot and click tests (`web/scripts/`). The hero image and logo are the lead's | Lead |
| 31 Oct 2026 | Teammate's coding agent | Teammate's round 1 (`advisor/`, `api/`, `quality/`, `ml/`, `neo4j/`, configs); details to be added from her report | Teammate |
