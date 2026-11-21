# Teammate: your plan from now to the end of the finale (21–22 Nov)

**From the lead, 21 Nov, about 12:00.** Part A is for you. Part B is one block to paste into your agent. The full plan is `PLAN.md` ("The 22 hours"); the runbook is `docs/runbook_finale.md`.

## Part A: your plan

**Your features:** **F3, debris on roads** (the trained model scores the roads), and **F4, the answer in Neo4j** (reach, clear first, fly next). F4 is the headline and the Neo4j track entry.

**What your model scored so far:** held-out IoU 0.24, recall 0.27 (`docs/teammate_finale_report.md`). It is a trained model and we call it that, always with this score next to it.

### Before we leave (now → 12:30)
| # | Do | Done when |
|---|---|---|
| 1 | ~~Copy the weights onto the demo laptop~~ **Done 21 Nov 12:25:** both files in `vortex/models/`, SHA-256 match your report | — |
| 2 | Get `labels.csv` from the lead (50 crops; she and you labelled them on 21 Nov) | You have it as a file, not a photo |
| 3 | ~~Nepal roads fetch~~ **Done 21 Nov 12:14 on the demo laptop:** 106,667 segments, 1,591 places. **85,625 of them are `unclassified` village roads**: for the Neo4j questions keep trunk, primary, secondary and tertiary (about 21,000), and say so | — |
| 4 | ~~Neo4j step 1.3~~ **Done on both laptops, 21 Nov.** Demo laptop: `.env` created with a local-only password (in the file, never in chat), GDS 2.13.14 answers, a restart uses the saved plugin. Its ports are now bound to the laptop only (`127.0.0.1`), so nobody on the venue Wi-Fi can reach it; the app is unaffected | — |

### In the car or on arrival (before 14:00): score the model on our 50 crops (agent step 1)
This is evaluation, not a feature: it can happen before 14:00. **Fix the rule before you look at the results** (see Part B). The labels: 30 debris, 11 no debris, 9 can't tell. **20 of the 30 debris crops are "broken trees mainly"**, which the training data (CAS: mud and rock) may not cover. Report those separately: it tells us what the model can and cannot see.

### Changed in your files by the lead's side (21 Nov, ~18:00, item 6 "access by role")
- **Sign-in is now on** (`auth/`). Every page and API call needs a session, except the landing page, `/health` and `/accuracy/spec`. Roles: operator, evaluator (judges), field team (one PIN per team). Codes live in `.env`; show them with `uv run python -m auth.codes`.
- **`advisor/routes.py`, `post_field_report`:** a signed-in request skips the per-report PIN, and a field team's report is stored with its team name (`Team A (callsign)`). With `VORTEX_AUTH=off`, your original PIN check runs unchanged. If you edit this function, keep that `session` block at the top.
- **Tests:** `tests/conftest.py` turns sign-in off for every test unless the test turns it on (`tests/test_auth.py`). Your tests need no change.
- **Your phone page works as before** once a team signs in at `/login` with its PIN (checked in a browser).
- **Item 4 (~18:15), also in your phone page:** `field.html` loads a new `/field-static/outbox.js` before `field.js`; in `field.js` the "no connection" branch of the submit handler now keeps the report in the phone's outbox (it sends itself when back in range). A "Save the map to this phone (PDF)" link is added under the scenario picker (`GET /field/map.pdf`, module `fieldkit/`). If you rework the submit handler, keep the `TyphonOutbox.keep(...)` call in its `catch`.

### Your two ideas, added as upgrades (lead's decision, 21 Nov)
From your innovation list, the lead picked two. They are **upgrades to F3 and F4, not new features**, because the AMA said the demo and final-day code carry the most weight, and these two show up in the demo. The others stay out tonight: they need data we do not have (satellite radar, power grid), internet, or new servers, or they already exist (population, exports, the situation report, the what-if taps in F5).

- **Idea 2 → "fly next" knows what the model is unsure about (part of F4).** Today, fly next ranks unknown roads by how many people's routes depend on them. Add the model's uncertainty: a road the model scored near 50/50 is worth a look more than one it is sure about. Score = people who depend on the road × (1 + w × uncertainty), with uncertainty from `p_blocked` (for example 1 − |2·p_blocked − 1|) and **w hand-set in config: it is a rule, called a rule, never AI.** Battery, airspace and flight cost are not modelled: list them as limits. *Done when:* the ranking on screen changes when a road's model score changes, and a test shows it.
- **Idea 7 → every model suspicion gets checked by a person (part of F3).** A model score above your threshold makes the road **"needs checking"**, never "blocked" and never "open". It carries its evidence crop, the score, the model version and the time. A field report from the phone (with the PIN) **confirms or rejects** it, and the road keeps a short history: *model said, person said, when*. Keep the history in `advisor/`'s own store; contracts are frozen, so if this needs a contract change, write the proposal and stop. *Done when:* a judge can tap a suspicious road on the phone, confirm or reject it, and the map shows the new status with its history within a few seconds.

### The 22 hours
| When | You | Done when |
|---|---|---|
| 14:00–15:00 | Set up with the team; collect the AuraDB access at the partner desk (from 14:30). Access goes in the local `.env` only | `advisor` reads from AuraDB, or the local container if AuraDB is not ready |
| 15:00–20:00 | **F3, part 1:** score every South Fork road segment from the orthophoto → `ml_scores.json`, with an evidence crop per segment | All 498 segments have a score; the file validates against `contracts/ml_scores.schema.json` |
| 20:00–21:00 | **Mentor Round 1 (40 marks).** Be able to explain your layer in two minutes: the model, its score, why it only raises "needs checking" | — |
| 21:00–23:00 | **F3, part 2:** hand `ml_scores.json` to the lead's side for fusion with the height check (`roads/`, lead's code). Fix what the lead finds. **Plus idea 7:** "needs checking" with evidence, confirmed or rejected by a field report, with its history | South Fork shows statuses that are not all "unknown", each with its evidence crop; a phone report confirms or rejects a suspicion |
| 23:00–04:00 | **F4:** reach per vehicle, clear first, fly next, **computed** in Neo4j with your plain-Cypher queries (no GDS plugin), checked against NetworkX, on Nepal and South Fork. **Plus idea 2:** the uncertainty term in fly next | Each answer is the same in Neo4j and NetworkX; "fly next" is a computed ranking that responds to the model's uncertainty |
| 01:00–04:00 (overlap) | Help the lead wire F5: a tapped road changes your graph and the answers refresh in seconds | Tap a road on the phone; clear first and fly next redraw |
| 04:00–07:00 | Join everything; run every demo action end to end twice; sleep in turns | Runbook passes twice |
| 07:00–07:30 | Progress post on Discord (required by 07:30) if you are the pitch owner's backup | Posted |
| **08:00** | **Code freeze.** Nothing new after this | — |
| 08:00–09:30 | Demo video: **your own voice** for the advisor part, on camera briefly | Recorded |
| 10:00–11:45 | Mentor Round 2 (60 marks) and the **Neo4j track review**: you run F4 live | — |
| by 11:30 | Submission (pitch owner) | Repo link, video, deck submitted |

**If we slip:** the history view (idea 7) and the uncertainty term (idea 2) go first; "needs checking" itself stays. Then F5 shrinks to "pick a vehicle" only. F3 and F4 are never cut. A fix that lands after 08:00 does not ship.

**Rules for the whole night:** work on `teammate` and ask before pushing; never force-push; no numbers that no run produced; a model score alone never sets a road to "open"; the rough map can only raise "needs checking", only the measured map can set "blocked".

---

## Part B: paste this into your agent

```
CONTEXT
You are working in the vortex repo (Project Typhon, team Vortex, hackFront T8.2 finale, 21-22 Nov 2026).
Read first: PLAN.md (section "The 22 hours", rows F3 and F4), docs/teammate_finale_report.md,
docs/eval_southfork_crops.md, contracts/ml_scores.schema.json, ml/train_debris.py, advisor/report.py,
advisor/neo4j_client.py.
Our debris model: models/typhon_debris_resnet18.pt / .onnx (U-Net, ResNet-18, trained on CAS Moxi 0.2 m;
held-out IoU 0.2373, recall 0.27). Training resolution 0.20 m per pixel, 512x512 tiles.

FILES
May change: ml/, advisor/, your own scripts in scripts/, your tests in tests/,
docs/teammate_finale_report.md, docs/runbook_advisor.md, docs/AI_DISCLOSURE.md (add rows only).
Read-only: contracts/ (frozen for the finale), web/, api/, pipeline/, roads/, measure/, accuracy/, export/,
PLAN.md. If a contract must change, write the proposal in your report and stop; do not edit it.
Never commit: data/, models/, .env, anything with credentials.

HARD RULES
1. No invented numbers. Every score comes from a run you can repeat; anything not run says PENDING.
2. A model score alone never sets a road to "open". Unknown stays unknown.
3. The rough map may only raise "needs checking"; only the measured map may set "blocked".
4. Hand-set rules are called rules, never AI. The model is called a trained model, with its score.
5. Contracts are frozen today. Work on branch `teammate`. Ask the lead before every push. Never force-push.
6. No internet at runtime. No AI co-author lines in commits; log AI use in docs/AI_DISCLOSURE.md.

STEPS
1. (Before 14:00) Score the model on our 50 crops.
   a. Write the rule into docs/teammate_finale_report.md BEFORE running anything: a crop counts as
      "debris" when the predicted debris share of the crop is at least T. Pick T from the CAS validation
      set only (not from these crops), and write T and how you chose it.
   b. Crops: data/eval/southfork_crops/c01.png ... c50.png (5 cm per pixel, 25.6 m across);
      resize to 0.20 m per pixel as in training. Labels: data/eval/southfork_crops/labels.csv
      (debris / clear / unsure). Leave out "unsure" and blank labels, and say how many were left out.
   c. Report precision, recall and the confusion table (counts). Report again for the crops whose
      notes say "broken trees" versus the rest. Write the script as ml/eval_crops.py so it reruns.
   d. Fill the "South Fork 50 Road Crops" row in the report. If the model does badly, say so plainly:
      that decides that F3 raises "needs checking" only.
2. (15:00-20:00) F3 part 1: for each South Fork road segment (
   the active project is in data/active.json: today southfork_f01_4, so data/projects/southfork_f01_4/roads/
   segments.geojson, 498 segments, orthophoto at the path in data/active.json), cut the orthophoto along its corridor, run the
   model, and write ml_scores.json per the contract (p_blocked, p_partial, p_clear, model, version) using
   your corridor_debris_fraction rule, labelled as a rule. Save one evidence crop per segment and list its
   path in your report. Validate against contracts/ml_scores.schema.json. Time the whole run.
2b. (21:00-23:00) Human check (idea 7): in advisor/ only, a segment whose model score passes your threshold
   becomes "needs checking" (never "blocked", never "open"), stored with its evidence crop, score, model
   version and time. A field report (existing phone page, PIN) on that segment confirms or rejects it; keep
   a history per segment: model said, person said, when. Keep the history in advisor/'s own store. Contracts
   are frozen: if this needs a contract change, write the proposal in your report and stop. Add a test:
   suspicion -> confirm -> status and history as expected; suspicion -> reject -> back to unknown.
3. (23:00-04:00) F4: put your three plain-Cypher queries (reach, clear first, fly next) into advisor/ so
   they run on AuraDB without GDS, with NetworkX as the fallback. Fly next must be computed: rank unknown
   roads by the population whose every possible route passes through them. Add tests that check Neo4j and
   NetworkX give the same answers on the Nepal and South Fork graphs. On screen, say which engine answered.
   Then (idea 2) multiply each fly-next score by (1 + w * uncertainty), uncertainty = 1 - |2*p_blocked - 1|
   from ml_scores.json (0 when the road has no model score). w is a hand-set value in config/ (a rule,
   documented as a rule, never called AI). List battery, airspace and flight cost as limits, not modelled.
   Add a test where changing one road's p_blocked changes the ranking.
4. After each step: uv run pytest -q, commit small with a clear message, and send the lead the commit hash,
   the pytest line and the new numbers.

DEFINITION OF DONE
- Step 1: report row filled from a rerunnable script, rule written before the run.
- Step 2: ml_scores.json for every segment validates; evidence crops exist; run time recorded.
- Step 2b: a suspicion can be confirmed or rejected from the phone; history kept; test passes.
- Step 3: three answers computed in Neo4j, same as NetworkX in tests; fly next responds to uncertainty;
  tests pass.

TIME LIMIT
Step 1 by 14:00. Step 2 by 20:00. Step 2b by 23:00. Step 3 by 04:00. If time runs short, drop the history
view and the uncertainty term first; "needs checking" itself stays. If something is impossible or will run more than an
hour past its slot, stop and tell the lead. Do not improvise a substitute.
```
