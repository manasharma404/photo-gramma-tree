# Offline phone check (about 15 minutes, lead + one phone)

Goal: prove a responder's phone can open the map and the field form from the laptop **with no internet anywhere**.
Already checked headlessly on the laptop (`web/scripts/offline_check.mjs`, 31 Oct 17:30 IST): landing, dashboard (desktop and phone width, all tabs, 3D) and `/field` made 81 requests, **none left the laptop**, no errors. What the phone test adds: the real network path, the firewall, and a real phone screen.

**Status (31 Oct 20:45 IST):** the teammate ran `/field` on an iPhone over her laptop's hotspot with no internet and submitted a report (`docs/teammate_report.md`, V3). Not yet done by a person: the dashboard `/app/` on a phone. Her firewall rule had no `-RemoteAddress LocalSubnet`; remove it after the event (`Remove-NetFirewallRule -DisplayName "Typhon Field Hotspot Port 8000"`).

## Network: the phone makes the hotspot (recommended)
Windows' own Mobile Hotspot usually refuses to start without an internet connection to share, so use the phone's hotspot instead:
1. Phone: **turn mobile data OFF**, then turn on its hotspot. (No mobile data = no internet for anyone.)
2. Laptop: unplug any cable, connect Wi-Fi to the phone's hotspot. Windows should say "No internet". That is the point.

## Laptop
3. Start the app (if it isn't already running): `uv run python -m api.main`
4. **Firewall (you run this; it's a security setting).** Open PowerShell **as administrator**:
   ```
   New-NetFirewallRule -DisplayName "Typhon demo 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -RemoteAddress LocalSubnet -Action Allow
   ```
   This allows only devices on the same local network, only port 8000. If Windows pops up its own "allow Python?" box instead, tick **Private** only.
5. Show the QR code: `uv run python scripts/qr.py`. It prints the address too (something like `http://192.168.x.x:8000/field`).

## Phone (write down pass / fail for each)
| # | Check | Pass looks like |
|---|---|---|
| 1 | Scan the QR | `/field` form opens |
| 2 | Submit one test report (label it TEST) | Confirmation shown; the report appears on the laptop dashboard |
| 3 | Open `http://<same address>:8000/app/` | Map with orthophoto and coloured road lines; panel readable at phone width |
| 4 | Tap a road segment | Its status and reasons show |
| 5 | Open `http://<same address>:8000/` | Landing page with the hero image |
| 6 | Take one screenshot of each of 1, 3, 5 | Proof for the deck |

## Afterwards
7. Remove the firewall rule (admin PowerShell):
   ```
   Remove-NetFirewallRule -DisplayName "Typhon demo 8000"
   ```
8. Tell Claude the pass/fail list and drop the screenshots in `data/screenshots/phone/`.

## If this breaks
| Symptom | Likely cause | Fix |
|---|---|---|
| Phone can't load anything | Firewall, or laptop on a different network | Re-check step 2 and step 4; on the laptop, `ipconfig` should show an address on the phone's network |
| QR shows a 127.x or wrong address | Laptop has several network adapters | `uv run python scripts/qr.py --ip <laptop address from ipconfig>` |
| Page loads but map is blank | Tiles not built for the active project | Tell Claude (`data/active.json`) |
| Windows hotspot used instead and won't start | Needs a connection to share | Use the phone hotspot as above |
