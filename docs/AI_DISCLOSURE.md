# AI disclosure

The hackFront rules require disclosure of AI-assisted work. One line per piece of work.

| Date | Tool | What it did | Reviewed by |
|---|---|---|---|
| 31 Oct 2026 | Claude Code (Claude Opus 5.5) | Drafted PLAN.md and TEAMMATE.md; machine and Docker checks; repo skeleton, .gitignore, contracts (JSON Schemas + mock examples) and their test | Lead |
| 31 Oct 2026 | Claude Code (Claude Opus 5.5) | Worked out the DJI Neo 2 telemetry layout from value ranges; wrote `pipeline/dji_telemetry.py`, `pipeline/frame_quality.py`, `pipeline/video_check.py` and tests | Lead |
| 31 Oct 2026 | Claude Code (Claude Opus 5.5) | Wrote `pipeline/subset.py`, `pipeline/run_odm.py`, `accuracy/find_targets.py`, `accuracy/compute_errors.py` and tests; ran ODM; analysed the single-strip accuracy failure; wrote `docs/validation.md`; reviewed and merged the teammate's branch; wrote her prompts (`docs/teammate_prompt.md`, `docs/teammate_followup_1.md`). Target IDs SF10/SF11 were confirmed visually by Claude and still need the lead's confirmation | Lead |
| 31 Oct 2026 | Teammate's coding agent | Teammate's round 1 (`advisor/`, `api/`, `quality/`, `ml/`, `neo4j/`, configs); details to be added from her report | Teammate |
