# Our own test set: 50 crops from the South Fork map (T2)

**Made 18 Nov 2026. Labels: PENDING (lead and teammate, together).** This set tests the debris model on our own map, separately from the held-out region of the training data. **It is never used for training.**

## Make it
```
uv run python scripts/make_eval_crops.py
```
Writes `data/eval/southfork_crops/` (not in git; the same seed gives the same crops every time):

| File | What it is | Share with the other labeller? |
|---|---|---|
| `c01.png` … `c50.png` | 512 × 512 px crops, 25.6 m across at 5 cm per pixel, north up | yes |
| `label.html` | The labelling page. Double-click to open; works offline | yes |
| `labels.csv` | Blank sheet: `crop_id, label, notes` | yes |
| `contact_sheet.jpg` | All 50 at a glance, ids only | yes |
| `crops_key.csv` | Where each crop came from: group, path piece, coordinates (EPSG:32611 and lat/lon) | **no, not before labelling is finished** |
| `where_crops_are_SHOWS_GROUPS.jpg` | The crops drawn on the map, coloured by group | **no, not before labelling is finished** |

`data/eval/southfork_crops_for_labelling.zip` holds only the shareable files (about 30 MB). Send it as a file, not as photos, so the images are not recompressed.

## Why not 50 road crops
The brief asked for about 50 road crops. Inside our map, the only roads are 16 OpenStreetMap footpath pieces (about 800 m in all), and **none of them crosses the debris channel**: both paths run through forest beside it. Road crops alone would be almost all "no debris", which tests false alarms but cannot show whether the model finds debris. So the set has three groups, chosen by a fixed rule, not by eye:

| Group | Count | Rule |
|---|---|---|
| path | 14 | The middle of each path piece inside the map. 2 of the 16 sit at the map's edge, where a full crop would run off it |
| bare | 18 | Random spots on pale bare ground: among the least green 15% and the brightest 15% of the map. Debris, trails and rock all look like this, so it holds hard cases both ways |
| random | 18 | Random spots anywhere on the map |

No two crop centres are closer than 30 m, so crops do not overlap. The first version of the "bare" rule (brighter than the median) mostly caught grey dead shrubs; it was tightened on 18 Nov **before any labelling**. On a first look, roughly 8 to 10 crops show debris: that is close to the most this map can give, because the channel only fits about that many separate crops.

## Labelling rules
- **Debris:** fresh landslide or debris-flow material anywhere in the crop: mud, loose rock and boulders, sand fans, broken or piled trees, a raw scar.
- **No debris:** none of that. Bare trails, old rock outcrops, dry grass and shadows are "no debris".
- **Can't tell:** too dark, too blurred, or hidden by trees. It is not counted as either.
- Label together and agree on each crop; write disagreements in the notes. Label what you see, not what you expect. Do not open the key file until all 50 are done.
- The page keeps labels in that browser until **Save labels.csv** is pressed. Save the file into `data/eval/southfork_crops/`, replacing the blank one.

## Scoring (teammate)
1. **Before looking at the labels**, write down the rule that turns the model's output for a crop into "debris" or "no debris" (for example: predicted debris covers at least 1% of the crop). Write it in `docs/teammate_finale_report.md` with the date.
2. Run the model on all 50 crops, resized to the training resolution recorded in T1.
3. Drop "can't tell" crops. Report precision and recall over all crops, and the counts per group (from `crops_key.csv`), **separately from the held-out region's scores**.
4. With about 10 debris crops, one miss moves recall by about 10 points. Report the counts next to every percentage (for example "7 of 9"), and call it a check on our own map, not a benchmark.
5. If the model does badly here, say so plainly: that result decides whether F3 sets a road status or only raises "needs checking".

## Limits
- One map, one site, one season. The debris here is a 2023 debris flow seen from 30 to 60 m up, in daylight.
- The path crops test false alarms along paths under trees, not debris on roads: no road in this map is buried.
- The groups come from a simple colour rule, not from a land-cover model.
