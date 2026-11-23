# Demo day: laptop to iPad, and every security concern

**For the lead, 22 Nov.** How to run the demo from the laptop with the judges on the iPad, what to say, what can go wrong, and every security concern with what to do about it. Numbers are from this morning's runs; anything simulated is said to be.

---

## 1. Who holds what

| Device | Who | What it shows | Signed in as |
|---|---|---|---|
| **Laptop** (projector) | Lead | Home page, the map (demo scenario), the Neo4j panel, the deck | **Operator** (can reset the demo) |
| **iPad** (in the judges' hands) | Judges | **Your teammate's live page `/field/map`**: tap a road, say what you see and how bad, send. It refreshes every 4 s | **Evaluator** (the code on the judges' card) |
| **Phone** (optional) | Teammate | The same page, as a field team | **Team PIN** |

All three join **the same small network**: a phone hotspot with **mobile data off**, or the laptop's own Mobile Hotspot. Not the venue Wi-Fi: it is marked *Public* on this laptop, and venue networks often stop devices talking to each other.

---

## 2. Setup, 30 minutes before (in this order)

**1.** **Network.** Hotspot on (mobile data off). Laptop joins it. iPad joins it. Check the laptop's address changed from the venue Wi-Fi (`10.202.65.213` this morning).

**2.** **Docker and Neo4j.** Docker Desktop running; Neo4j is a container that only this laptop can reach:

```powershell
docker start t82-neo4j
```

**3.** **The app.** It was restarted at 08:37 with today's code and runs in a minimized window (`uv run python -m api.main`). Check it answers: open `http://localhost:8000/health` on the laptop. If you ever restart it: Ctrl+C in that window, then:

```powershell
uv run python -m api.main
```

**4.** **QR code for the iPad: your teammate's live page.** In a terminal in the project folder (`C:\Users\HP\Desktop\hackfront\vortex`), **after** joining the hotspot:

```powershell
uv run python scripts/qr.py --path "/field/map?project=demo"
```

This opens her page on the **demo scenario, the same one the laptop map shows**, so a road reported on the iPad changes on both screens. For her own Wayanad scenario (from the 2024 reports: hundreds of blocked and partly blocked roads), use `?project=wayanad` instead; reports there do not show on the laptop's demo map. If the QR shows the wrong address (it picks the network itself), give the hotspot address, for example Windows Mobile Hotspot:

```powershell
uv run python scripts/qr.py --ip 192.168.137.1 --path "/field/map?project=demo"
```

**5.** **iPad sign-in.** Scan the QR, sign in with the **evaluator** code from the card. Never type a code where the projector can see it. **After signing in the page may open on the South Fork survey** (the sign-in loses the `?project=` part): pick **demo** in the project menu at the top of the page, or scan the QR again (now signed in, it goes straight there).

**6.** **Reset the demo.** On the laptop map, Overview card (bottom left) → **Reset demo** (operator only). For the Wayanad scenario, in a terminal: `uv run python scripts/reset_demo.py --project wayanad`. Do it before every round.

**7.** **Fallback ready.** `docs/demo/motion/out/typhon_demo_finale.mp4` (75 s) on the laptop and on a phone, plus the deck PDF. If anything fails, play the video and keep talking.


---

## 3. The demo, about 3 minutes

| Time | Device | Do | Say |
|---|---|---|---|
| 0:00 | Laptop | Home page | "One drone, one laptop, no internet: a map and a decision in the first hours." |
| 0:15 | Laptop | **Open the map** (it opens on the demo) | "This is a **simulated** landslide on the **real roads** of Wayanad. Our own flights had no landslide, so we made up the damage and the people to show what Typhon decides." |
| 0:35 | Laptop | Vehicle: **Ambulance**, then **On foot** | "205 people in 11 groups. For an ambulance 148 are cut off; on foot, 55. Each blockage lets different vehicles through." |
| 1:00 | Laptop | Point at the **Neo4j panel** | "NetworkX answers at once so the map updates; Neo4j computes the same answer in the background and confirms it." |
| 1:15 | **iPad** | Hand it over on your teammate's page: "Tap any open road, say what you see (debris, dead end) and how bad, then send." | "This is a field team reporting from the ground. Watch the plan change." |
| 1:30 | Both | The road turns blocked on the iPad within about 4 s; the laptop map recomputes within about 3 s and a notice says what changed (people cut off go up; Clear first changes). Then report it **cleared** and watch it come back | Example on the laptop: clearing the **damaged bridge** takes the jeep's count **from 94 to 55**. |
| 2:00 | Laptop | Act now → **Plan a re-fly** on the blurred patch | "Roads the photos couldn't show stay unknown. One click plans a re-fly: 14 passes, about 19 minutes (an estimate)." |
| 2:30 | Laptop | Optional: Site → **real survey** | "On real survey photos: ±6.06 m at 3 checkpoints, no ground control; 13.14 ha in 80.2 min on this laptop." |
| 3:00 | Laptop | Back to the deck | The three judging criteria. |

**Teammate's phone (optional):** the same page with a team PIN; her reports land on both screens the same way.

### When no roads are blocked
- **On the South Fork survey nothing is blocked**: the drone photos show no damage on those roads, and the roads under tree canopy are "unknown". That is honest, so don't demo decisions there; use it only for the accuracy and timing story.
- **Use a project that has trouble on it:** `demo` (4 blockages, a blurred patch, 205 simulated people; the same as the laptop map) or `wayanad` (her scenario from the 2024 reports).
- **Or make the blockage live, which is the point of the demo:** a judge taps an open road on the iPad and reports debris; the plan recomputes on both screens; then they report it cleared and it comes back. Reset afterwards.

---

## 4. If a judge asks

| Question | Answer |
|---|---|
| "Is this real?" | "The roads are real OpenStreetMap data. The damage and the people are simulated, and the map says so. The map-making itself was measured on real survey photos." |
| "How accurate?" | "±6.06 m at 3 surveyed checkpoints, with no ground control. 3 is a small sample; the standard asks for 30. Our own survey with 30 checkpoints is next." |
| "Why two numbers for time?" (the map's accuracy box shows 145.6 min, the home page 80.2) | "Two real runs on this laptop: 145.6 min was our first quick run on 31 Oct; 80.2 min is our default since 4 Nov. The deck lists all four runs." |
| "Why is Neo4j slower?" | "On 1,568 roads it takes 12 to 23 s depending on load; NetworkX answers first, Neo4j confirms the same answer. We fixed a missing index this morning that made it take 108 s." |
| "Does it need the internet?" | "No. 0 of 128 page requests left the laptop in this morning's check." |
| "Is it live from the drone?" | "The growing map is replayed from disk in the demo; it places each photo about a second after it arrives on an idle laptop." |

---

## 5. Security concerns, and what to do about each

### Do now
1. **The Cloudflare tunnel is still open** (since 20:06 last night). It puts the app's sign-in page on the public internet; it was opened for the ArgosX scan only. If the scan is done, close it: press **Enter** in the tunnel window (the one that ran `scripts/argosx_tunnel.ps1`). Re-open it with the same script only for the final scan, then close it again.
2. **Team PINs appeared in our chat this morning.** Treat them as seen. After the demo (or before, if the chat is shared), make new ones in **your own terminal, not on the projector** with `uv run python -m auth.codes`, then restart the app. New PINs mean new cards for the field teams. The operator and evaluator codes were not shown.
3. **Close my test browser.** A headless Edge with a debugging port (`127.0.0.1:9223`) is still running from today's checks. It answers only on this laptop, but any program on the laptop could drive it. Close it after the session.

### During the demo
4. **Plain HTTP on the hotspot.** There are no certificates on a hotspot, so sign-in codes travel unencrypted on that network. **The hotspot password is the barrier:** use a strong WPA2 password and give it only to the team's devices and the judges' iPad.
5. **Never show codes on the projector.** `uv run python -m auth.codes` prints all codes; run it on the laptop only when the projector is off or on another window. The app's own window does not print codes.
6. **Venue Wi-Fi is Public.** The app listens on every network the laptop joins (`0.0.0.0:8000`), so on the venue Wi-Fi anyone there could reach the sign-in page. Use the hotspot; leave the venue Wi-Fi during the demo if you can.
7. **Judges can change the demo.** The evaluator role can view everything, file road reports, start a growing-map replay and run measurements; it cannot reset the demo. **Reset between rounds** (Overview → Reset demo).
8. **Wrong codes lock a device out for 10 minutes** after 5 tries. If a judge mistypes, give them a second device or wait it out; do not turn sign-in off.

### Already in place (each has a test: home page section "Security")
- Sign-in by role (operator, evaluator, team PIN); one gatekeeper checks every request.
- Signed session cookie: HttpOnly (scripts cannot read it), SameSite=Strict (other sites cannot use it), expires after 12 hours.
- Database queries use placeholders: injected text is stored as plain text.
- Map tiles cannot read files outside the tiles folder.
- After sign-in, only links inside the app are followed.
- **Neo4j only answers on this laptop** (127.0.0.1:7474 and 7687); its password is in `.env`.
- **No secrets in git:** `.env` is ignored; nothing secret is tracked.
- Everything runs offline; the public GitHub Pages copy is read-only and holds only public data.

### Still open, said plainly
- The independent **ArgosX scan report is PENDING** (baseline due last night, final due 11:00).
- No HTTPS on the hotspot (see 4).
- One shared evaluator code for all judges.

---

## 6. After the demo
1. Close the tunnel if it is open; close the test browser.
2. Make new team PINs (5.2) if the chat or the cards went around.
3. Reset the demo, so the next round starts clean.
