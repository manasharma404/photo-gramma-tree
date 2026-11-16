# Finale groundwork for the teammate's agent (17–19 Nov)

**Status: DRAFT from the lead's side, 16 Nov. The lead approves it before you start.** Paste everything below the line into your agent, run from the root of the `vortex` repo.

**Send back by Thu 19 Nov, 22:00 IST:** the list in section 6.

**Update, 17 Nov (one change, in T4):** the case study is now **Nepal, the flash flood of 26 August 2026** (Rasuwa, Nuwakot and Dhading), not Kedarnath. The lead decided this on 17 Nov. The video opens with that event, so the pitch, the video and your pack must use the same event and the same cited figures. T1, T2 and T3 are unchanged.

---

## 1. Context
- Product: **Project Typhon** (team Vortex), hackFront PS T8.2 "The First Map After The Landslide". We are finalists. The finale build runs **Sat 21 Nov 14:00 to Sun 22 Nov 12:00** at IIIT Delhi.
- Judges weight what is built in those 22 hours. This week is groundwork only: data, a trained model, and checks that remove unknowns. The features themselves get built at the finale.
- The plan is in `PLAN.md`, section "Finale plan". Read it first. Your finale features are **F3** (debris on roads) and **F4** (the answer and the plan in Neo4j).
- The biggest flaw we are fixing: on our real drone map, **all 498 South Fork road segments read "unknown"** for every vehicle. Your model is what gives the first real answers.

**Read before you start:** `PLAN.md` (Finale plan), `ml/road_damage.py`, `contracts/ml_scores.schema.json`, `advisor/assess.py`, `advisor/report.py`, `advisor/neo4j_client.py`, `scripts/prefetch_wayanad.py`, `docs/sources_teammate.md`.

```
git fetch origin
git checkout teammate
git merge origin/main
uv sync
uv run pytest -q
```

## 2. Files you may change
- **May change:** `ml/`, `scripts/` (new prefetch and training scripts), your tests, `docs/sources_teammate.md`, `docs/runbook_advisor.md`, `data/LICENSES.md` (add rows only), and a new `docs/teammate_finale_report.md`.
- **Read-only this week:** `advisor/`, `api/`, `quality/`, `export/`, `web/`, `pipeline/`, `accuracy/`, `measure/`, `roads/`, `contracts/`, `config/`, `PLAN.md`. If a contract needs to change, write the proposal in your report; do not edit it.
- **Never commit:** datasets, model weights, anything under `data/` except `data/LICENSES.md`. Record each large file's name, size and SHA-256 checksum in your report instead.

## 3. Hard rules
1. **No invented numbers.** Every score in your report comes from a run you can repeat. Anything not run says `PENDING`.
2. **The test images are never trained on.** One whole region of the dataset is held out before training starts, and the hold-out is named in the report.
3. **Unknown is not open and not blocked.** A model score alone never sets a road to "open".
4. **Licences first.** Before using any dataset subset, record its licence and terms. If a subset's terms are unclear, do not use it.
5. Hand-set rules are never called AI. A trained model is called a trained model, with its measured score next to it.
6. Work on `teammate`. Never push to `main`. **Ask the lead before pushing.** Never force-push. No AI co-author lines in commits; log AI use in `docs/AI_DISCLOSURE.md`.
7. Nothing from this week may need the internet at runtime.

## 4. Steps, in this order

### T1. One model, one job: find landslide debris in drone maps (Tue–Thu, about 12 hours of work plus training time)
1. **Data.** Download the **CAS Landslide Dataset** (Zenodo record 10294997, about 9.2 GB; Xu et al., Scientific Data 2024). Use only the **drone (UAV) subsets**. The overall licence is CC BY-NC 4.0, and the README lists different terms for some subsets: copy each used subset's terms into `data/LICENSES.md`.
2. **Do not download** SpaceNet 8, FloodNet or CRASAR-U-DROIDs. The first two are floods seen from satellites or at an angle; the third is 219 GB with no landslides. The reasons are in `PLAN.md`.
3. **Record the ground resolution** (metres per pixel) of every subset you use. Our maps are 5–10 cm per pixel, so at prediction time our crops are resized to the training resolution. Write the chosen resolution down.
4. **Hold out one whole region** as the test set before any training. Split the rest into training and validation.
5. **Train a small segmentation model** (debris or not, per pixel) that runs on the lead's laptop: RTX 4050 with 6 GB, or CPU. A backbone pretrained on ImageNet is fine; name it in the report.
6. **Measure** on the held-out region: IoU (overlap between predicted and true debris area), precision and recall. Then measure the unchanged CRASAR road model on the same images if its weights load, as the comparison. If they do not load, write "not compared" and why.
7. **Export** the weights to ONNX and time one 512 × 512 prediction on CPU and on GPU.
8. **Keep the contract.** The output per road segment stays `ml_scores.json` (`p_blocked`, `p_partial`, `p_clear`, `model`, `version`). Write down, in the report, the rule you propose for turning a debris mask into those three numbers (for example, the share of the road corridor covered). That rule is a proposal for the finale, labelled as a rule.

**Done when:** a weights file exists outside git with its checksum; the report has a score table from a repeatable run; a script reproduces the scores from the downloaded data.

### T2. Our own test set (Wed, 2 hours, with the lead)
The lead's side will send about 50 road crops from the South Fork map. Label each "debris on road" or "clear" with the lead, then run the model on them. Report precision and recall on these separately from the held-out region. **If the model does badly on our own map, say so plainly:** that result decides whether F3 sets a status or only raises "needs checking".

### T3. Neo4j: check what the finale instance can do (Tue, 2 hours)
At the finale we get a hosted Neo4j (AuraDB). Our access report uses the Graph Data Science plugin (`gds.allShortestPaths.dijkstra` in `advisor/report.py`), and **as far as we know, free AuraDB instances do not include that plugin (not verified by us: step 2 checks it).**
1. Create a free AuraDB instance with a throwaway account of your own (no credentials in the repo or in chat; use a local `.env`).
2. Run `advisor/load.py` and the access report against it. Record exactly what fails.
3. Write down, as plain Cypher that needs no plugin, how to answer these three questions. Test each on the Wayanad graph and check it gives the same answer as the NetworkX fallback:
   - **Reach:** which settlements can each vehicle reach from the base, counting only roads known to be open?
   - **Clear first:** which single blocked road, once cleared, reconnects the most people?
   - **Fly next:** which unknown road, once surveyed, would settle the route for the most people? (Rank unknown roads by the population whose only possible routes pass through them.)
4. Do **not** build these into `advisor/` this week. The queries and their test results go in the report; the feature is built at the finale.

**Done when:** the report says what works on a free instance, and has three tested queries with their results next to the NetworkX results.

### T4. Nepal scenario pack (Wed–Thu, 3 hours)
The case study for the pitch and the video is the **flash flood of 26 August 2026 in Nepal**, set off by a glacier collapse and a landslide on the Nepal–China border. It joins as a **scenario reconstructed from reports**, the same kind as Wayanad, never as something our drone measured.

**What the lead's side read on 17 Nov** (leads to check, not facts to copy: open each article and cite it yourself):
- Kathmandu Post, 29 Aug 2026, citing the Department of Roads: about 40 km of road damaged between Rasuwagadhi and Malekhu; 41 bridges destroyed or damaged. https://kathmandupost.com/national/2026/08/29/washed-out-bridges-force-flood-hit-communities-to-rely-on-choppers
- Same article, by place: the Trishuli river bridge at Trishuli Bazar swept away; every bridge between Trishuli and Betrawati washed away; the road to Dhunche and Rasuwagadhi heavily damaged; the Phurke Khola bridge at Malekhu washed away; three bridges between Galchhi and Malekhu destroyed, cutting Dhadingbesi off; the Baireni–Mugling section of the Prithvi Highway blocked for three days, then reopened.
- UN News, 31 Aug 2026: roads passable only as far as Nuwakot; access named as the biggest obstacle to the response. https://news.un.org/en/story/2026/08/1168233

1. Copy the approach of `scripts/prefetch_wayanad.py` into a new `scripts/prefetch_nepal.py`: OpenStreetMap roads and bridges for the corridor Galchhi – Trishuli (Bidur) – Betrawati – Dhunche – Rasuwagadhi, plus Malekhu – Dhadingbesi, with settlements and facilities. Keep it to this corridor: 3 hours, not the whole country.
2. Road and bridge states come only from cited reports, each with a specific URL and date in `docs/sources_teammate.md`. No report, no state: it stays unknown. A road that was blocked and later reopened is recorded with both dates.
3. Population figures are real cited numbers (census or municipality) or `null`. Never zero, never guessed.
4. **Deaths and missing people are not part of the pack and are never used as a hook.** If the pitch states a toll, it gives the figure, its date and its source (the UN gave 903 confirmed dead and more than 4,200 missing on 31 Aug 2026; later counts are higher and we have not verified them).
5. Write the limits in the report: today's OpenStreetMap may already show repairs or may not match 26 August; we have no drone imagery of it; nothing here is a measurement.
6. If your reading gives different figures from "about 40 km" or "41 bridges", tell the lead at once: the video shows both numbers.

**Why it is worth doing:** one valley, many breaks, and help that could only drive part of the way. Which break to clear first, and which stretch to fly next, are real questions here, so T3's queries have something to answer.

**Done when:** the pack loads offline through the same loader as Wayanad, and T3's three queries run on it.

## 5. Definition of done
- `uv run pytest -q` passes, with the counts in the report.
- `docs/teammate_finale_report.md` exists with: the licence table, the score tables (held-out region and our own crops, separately), timing, the AuraDB findings, the three queries with results, the Nepal pack's limits, and a list of anything that stayed `PENDING`.
- Nothing large is committed. Nothing is pushed without the lead's yes.

## 6. Send back by Thu 19 Nov, 22:00 IST
1. Branch name and commit hash.
2. The `pytest` summary line.
3. The report file.
4. Where the weights file is, its size and checksum.
5. Anything that turned out impossible, and why.

**If something is impossible or will run more than 2 hours past its slot, stop and tell the lead. Do not improvise a substitute.**
