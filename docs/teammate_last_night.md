# Prompt for the teammate's agent: the last night (21 Nov 23:45 → 22 Nov 08:00 freeze)

Paste everything below the line into your agent, on your laptop, in your clone of `manasharma404/photo-gramma-tree`, branch `teammate`.

---

## 1. Context

You are helping the teammate on Project Typhon (hackFront India 2026 finale, PS T8.2). Code freeze is **08:00 on 22 Nov**; anything that lands after 08:00 does not ship.

**What the lead checked at 23:40 on 21 Nov:**
- Your branch `teammate` (latest commit `79df2bc`) was merged with the current `main` (`67cffb1`) in a scratch copy on the demo laptop.
- There was **one conflict only**, in `docs/AI_DISCLOSURE.md`. Both sides had added table rows; keeping both fixes it.
- Full tests on that merge: **128 passed, 5 skipped, 1 failed**.
  - The failure is `tests/test_ml_scoring.py::test_ml_scores_schema_compliance`.
  - It fails because `data/projects/southfork_f01_4/ml_scores.json` is not in git (`data/` is ignored) and isn't on the demo laptop.
- The demo laptop has the model file but **not** `onnxruntime`, so it can't re-score. It needs your output files.
- Your other numbers (IoU, precision/recall, 1.53 s, 498 roads) are quoted from your report; they were not re-run on the demo laptop.

**Your job tonight: finale item 5, "the judges' own input on the iPad".**
- A judge taps a road to block it, or picks a vehicle.
- The answer redraws in seconds: which places are cut off, what to clear first, where to fly next.
- The page says whether Neo4j or NetworkX answered.
- You own this page from start to finish, and it runs on your iPad in the demo.

**Read these first:**
- `docs/finale_build_plan.md`: items 3, 4 and 5, plus "If we slip".
- `auth/core.py`: the roles. Read it only; don't change it.
- `api/main.py`, lines 100–140: how `/advisor` is mounted and how `/field` and `/field-static/` are served.
- `advisor/routes.py`, `advisor/graph.py`, `advisor/report.py`, `advisor/store.py`, `config/priority.yaml`.
- `advisor/static/field.html` and `field.js`: your phone page.

## 2. Files you may and may not change

**You may change:**
- `advisor/**`; new files are fine
- `config/priority.yaml`
- `tests/test_advisor_*.py`, `tests/test_ml_scoring.py`, `tests/test_plain_cypher_and_fly_next.py`, and new `tests/test_whatif*.py`
- `docs/teammate_finale_report.md`
- `docs/AI_DISCLOSURE.md`: add your own rows only
- new screenshots in `docs/demo/ipad/`

**You may not change:**
- `web/**`: the lead is redesigning it tonight
- `auth/**`, `api/**`, `contracts/**` (frozen)
- `pipeline/`, `roads/`, `measure/`, `accuracy/`, `export/`, `.gitignore`
- anything under `data/` in git

If you need a change in one of these, stop and ask the lead.

## 3. Hard rules

1. **Never invent a number.**
   - Every figure on the page comes from the API.
   - Populations without a source show `PLACEHOLDER`.
   - A missing value shows "not measured yet".
2. **The model never decides alone.** A model suspicion shows as "needs checking", never as "blocked" or "open". Hand-set rules (like `w = 0.50` in `config/priority.yaml`) are called rules, never AI.
3. **A judge's test changes nothing real.**
   - It is computed fresh from the request and stored nowhere.
   - It never touches the field reports, `/advisor/state` or `/advisor/history`.
   - So judges can't spoil the field team's map, and no "reset demo" is needed.
4. **Offline:** no CDN, no web fonts, no internet map tiles. Everything is served by our app.
5. **Git:**
   - work only on `teammate`
   - ask the lead (the person) before every push
   - never force-push, never rewrite history
   - no AI co-author lines in commits; log AI help in `docs/AI_DISCLOSURE.md`
6. **Secrets:** never print `.env` values, PINs or access codes in chat or in files.
7. If something is impossible, or will take more than 45 minutes beyond this plan, **stop and tell the lead instead of improvising.**

## 4. Steps

**Step 1. Bring `main` into your branch (00:00–00:30)**
1. Run:
   ```
   git fetch origin
   git checkout teammate
   git pull
   git merge origin/main
   ```
2. In `docs/AI_DISCLOSURE.md`, keep both sets of rows. Delete only the `<<<<<<<`, `=======` and `>>>>>>>` lines.
3. In `tests/test_ml_scoring.py`, call `pytest.skip("…not in git; copy it from the teammate")` when `ml_scores.json` or the `evidence/` folder is missing. `data/` is never in git, so a fresh clone must skip, not fail.
4. Run the full tests. Expect **0 failed**.
5. Commit the merge, but don't push yet.

**Step 2. Send the lead your model output (by 00:45)**
- Zip:
  - `data/projects/southfork_f01_4/ml_scores.json`
  - `data/projects/southfork_f01_4/evidence/` (498 JPEGs)
  - every other copy your code reads (your report mentions a copy in `roads/`)
- Send it on WhatsApp **as a document**, not as a photo.
- Tell the lead the zip size and the exact paths inside it.

**Step 3. The what-if endpoint (00:45–02:00)**
- Add `GET /advisor/whatif?project=<p>&block=<seg_id,seg_id,…>&vehicle=truck|jeep|foot&backend=auto|neo4j|networkx`.
- It returns the same shapes as `/advisor/access` and `/advisor/priorities`, computed as if the listed roads were blocked, plus:
  - `engine`: `"neo4j"` or `"networkx"`
  - `seconds`
  - `blocked_by_judge`: the list
- **Why GET:** a signed-in evaluator may already GET everything, so the sign-in rules need no change.
- **Read-only:** it writes nothing to the store.
- **Input checks:**
  - an unknown segment id returns 422
  - at most 50 ids
  - the vehicle must be one of the three
- **Tests:**
  1. Blocking the only road to a place makes that place cut off for that vehicle.
  2. Neo4j and NetworkX give the same answer for 3 what-ifs. Skip the Neo4j half when Neo4j isn't running, as your other tests do.
  3. Calling `/advisor/whatif` leaves `/advisor/state` and `/advisor/history` unchanged.

**Step 4. The iPad page (02:00–04:00)**
- **Serving:**
  - the HTML at `GET /advisor/ipad`, from your router
  - the JS and CSS in `advisor/static/` (served at `/field-static/`)
  - `/advisor/context` has no road lines, so add a small read-only GET in your router that returns them
- **Roads:**
  - drawn as SVG from the segment lines; no map library, no tiles
  - each status shown by **shape or pattern as well as colour**:
    - open: solid
    - partial: dashed
    - blocked: solid with ✕
    - unknown: grey hatch
    - needs checking: amber outline
- **Controls:**
  - tapping a road toggles "blocked (judge's test)"
  - a vehicle picker: truck / jeep / foot
  - a "Clear my changes" button
- **Answer panel:**
  - places cut off for that vehicle
  - clear first (top 3) and fly next (top 3)
  - "answered by Neo4j in X s" or "answered by NetworkX in X s"
  - the line "Judge's test: nothing here changes the field team's map"
- **Size and feel:**
  - iPad landscape 1180×820 and portrait 820×1180
  - every tap target at least 44 px; give roads a wider invisible tap line
  - text at least 16 px
  - one request per change; show "working…" if it takes over 300 ms

**Step 5. Check it on your real iPad (04:00–05:00)**
1. Put your laptop and iPad on the same hotspot.
2. Sign in as evaluator. Get the code from the lead in person; never paste it into chat.
3. Open `http://<laptop-ip>:8000/advisor/ipad`.
4. Do 5 taps and write down the time the page shows for each.
5. Stop Neo4j (`docker stop t82-neo4j`) and tap again. The page must say NetworkX answered.
6. Save screenshots in `docs/demo/ipad/` (PNG, under 300 KB each).

**Step 6. Report and push (by 05:00)**
- Ask the lead, then push to `teammate`.
- Send the lead:
  - the commit hash
  - the test line (passed / skipped / failed)
  - the 5 answer times
  - the Neo4j-off result
  - the screenshot paths
  - anything not done

**Step 7. Rehearsal (05:00–07:30)** with the lead on the demo laptop:
- the offline runbook end to end, twice
- Wi-Fi off, hotspot on
- `/field` reports, the iPad page and the PDF map

Freeze is at 08:00. The video recording is 08:00–09:30, with your advisor segment in your own voice.

## 5. Definition of done

- [ ] `teammate` contains `main`; full tests show 0 failed.
- [ ] The zip of `ml_scores.json` and `evidence/` was sent to the lead, with its size and paths.
- [ ] `GET /advisor/whatif` exists with its 3 tests, read-only.
- [ ] `/advisor/ipad` works on your real iPad: 5 timed taps, and the NetworkX fallback is shown when Neo4j is off.
- [ ] Screenshots in `docs/demo/ipad/`; the report was sent; you pushed after asking.

## 6. Time limit and the fallback

- **Hard stop for code: 05:00.**
- If the tap-to-block page isn't working by **04:00**, shrink item 5 to "pick a vehicle only". This is the plan's own fallback.
- If something is impossible, stop and tell the lead with your options. Don't improvise around it.

## What to send back to the lead (copy, fill in, send)

```
TEAMMATE REPORT <time>
Merge of main into teammate: done / not done — commit <hash>
Tests: <passed> passed, <skipped> skipped, <failed> failed
Zip sent: <size> MB, paths: <list>
/advisor/whatif: done / not done — tests: <names>
/advisor/ipad on my iPad: 5 taps = <t1> <t2> <t3> <t4> <t5> s, engine = <neo4j/networkx>
Neo4j stopped → page said: <text>
Screenshots: docs/demo/ipad/<files>
Pushed to teammate: yes/no (asked lead: yes/no)
Not done / problems: <list>
```
