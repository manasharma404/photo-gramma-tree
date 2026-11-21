# Mentor prep, Round 1 (21 Nov): answers to the briefing questions

Only measured facts; anything not yet done says PENDING. Sources: `docs/validation.md`, `docs/finale_build_plan.md`.

## The deadlines that gate us (from the organisers' brief)
| When | What | Owner | State |
|---|---|---|---|
| **Today 16:00** | One-page Finale Build Plan (`docs/finale_build_plan.md`) | Lead submits | Draft ready |
| Mentor Round 1 | Plan may be revised once, with the mentor's sign-off; then locked | Lead | — |
| **Today 23:59** | ArgosX baseline scan; download the report | Lead + Claude | PENDING: find out what ArgosX scans (a URL or the repo) |
| **Sun 11:00** | ArgosX final scan + remediation log (found / fixed / remaining and why) | Lead + Claude | PENDING |
| **Sun 12:00** | Live build evaluators can use without us; Market Fit Canvas; 3 Customer Test; Persona Use Case Matrix | All | PENDING |

## 1. What did we do in the first 2 hours, and what are we building in the next 20?
- Before 14:00 (tagged `finale-start`): pipeline, accuracy, measurements, phone reports, Neo4j graph, a trained debris model, a test flight of our own with its GPS log (map within a median 1.4 m of the GPS track).
- 14:00–16:00: read the brief, set up, tagged the starting point, wrote the Build Plan.
- Next 20 hours: the seven items in the Build Plan, in that order.

## 2. Product-market fit, business plan, user market
- **First user (hypothesis until tested):** the officer running a district emergency operations centre in a landslide-prone hill district.
- **Payer (hypothesis):** the State Disaster Management Authority, equipping its district centres. PENDING: confirm with a real person who buys for a district or state centre.
- **Pricing hypothesis:** PENDING (the canvas needs a number; the lead decides it).
- **Market size with a source:** PENDING (research during the night; nothing quoted until it has a source).
- **The 3 Customer Test:** three real people from the segment, by phone, during the finale. PENDING: names. The lead's contact (via her father) is one lead; NDRF, SDRF, fire service or district officials are the target.

## 3. Segments and ideal customer: user level and institution level
| Level | Primary | Second | Third |
|---|---|---|---|
| Institution | District Disaster Management Authority (its emergency operations centre) | State Disaster Response Force, NDRF battalions, fire services | Public Works Department, Border Roads Organisation |
| User | Duty officer deciding where vehicles go in the first hours | Field team leader on the ground with a phone | Engineer planning clearance machines and bridging |

## 4. How secure is it? ("Vibe coded is accepted but must be secured")
- **In place today:**
  - nothing leaves the laptop at runtime (offline check: 0 requests left the laptop);
  - field reports need a PIN;
  - Neo4j listens on the laptop only (fixed 21 Nov);
  - passwords live in a git-ignored `.env`, never in the repo.
- **Known gaps (being fixed tonight):**
  - no login on the dashboard;
  - one shared PIN;
  - plain HTTP on the local network;
  - no limit on PIN guesses.
- **Plan:** ArgosX baseline scan, fix critical and high first, final scan, remediation log that explains what remains.

## 5. Scalability: what if 1,000 people use it at once?
- **By design:** one laptop serves one incident: a response centre plus its field teams, tens of devices, not 1,000 public users.
- **Scaling out:** more incidents means more laptops, each independent; when a network exists, each can send its map to a state centre.
- **The honest number:** PENDING. Tonight we load-test the laptop and report how many devices it serves before it slows down, measured, not guessed.

## 6. "Five problems with one tool"
One flight answers five questions a district needs in the first hours:
1. What does the ground look like now? (the map)
2. Which roads can each vehicle use? (road status)
3. Which blockage do we clear first? (Neo4j)
4. Where do we fly next? (Neo4j)
5. How big is the job? (debris volume, gap span, landing zones)

## 7. Real-world market analysis: how prepared are we?
Honest answer: weakest area today. Before the finale we sourced the case (Nepal, Aug 2026: 41 bridges, about 40 km of road damaged, access called the biggest obstacle; sources in `docs/demo/motion/storyboard.md`). Not yet done: market size, competitor pricing, conversations with buyers. Plan: the canvas and three customer calls tonight.
