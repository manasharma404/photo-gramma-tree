# Vortex Route Advisor & Field Responder Runbook

This runbook starts the **Vortex Route Advisor**, **Neo4j GDS**, **FastAPI app shell (`0.0.0.0:8000`)**, and **offline smartphone `/field` page** on a clean Windows clone for the live offline demo.

---

## 1. One-Time Setup (While Online)

Run these commands once from the repository root in **PowerShell** before disconnecting Wi-Fi.

### Step 1.1 — Install Python environment
```powershell
uv sync
```
**Expected output:**
```text
Resolved ... packages in ...ms
Audited ... packages in ...ms
```

### Step 1.2 — Create gitignored `.env` for Neo4j
Copy `neo4j/.env.example` to `.env` in the repository root and set a local password:
```powershell
Copy-Item neo4j\.env.example .env
# Edit .env and replace CHANGE_ME_LOCAL_ONLY with any strong local password (>= 8 chars), e.g.:
# NEO4J_AUTH=neo4j/vortexLocalDemo2026
# VORTEX_NEO4J_URI=bolt://127.0.0.1:7687
```
*(Important: keep `VORTEX_NEO4J_URI` prefixed with `VORTEX_`, because Neo4j's Docker entrypoint treats arbitrary `NEO4J_*` variables as `neo4j.conf` keys.)*

### Step 1.3 — One-time online Neo4j + GDS plugin bootstrap
Start the pinned Neo4j Community `5.26` container once while online so Docker pulls the image (`neo4j:5.26-community@sha256:249a1ec6e3c52d82101a5ed33d6ed2b5ed5b0017b21a28c0bfebc335e87fb177`) and caches `graph-data-science.jar` into `neo4j/plugins/`:
```powershell
docker compose --env-file .env -f neo4j/docker-compose.yml up -d
```
Wait ~45–90 seconds on first boot while `neo4j/plugins/graph-data-science.jar` (~65.8 MB) downloads, then verify GDS:
```powershell
Get-Item neo4j\plugins\graph-data-science.jar
uv run python -c "from advisor.neo4j_client import open_driver; d = open_driver(timeout_s=5.0); print(d.execute_query('RETURN gds.version() AS v').records[0]['v']); d.close()"
```
**Expected output:**
```text
2.13.14
```
*(How offline restart works: `neo4j/docker-compose.yml` checks if `/plugins/graph-data-science.jar` already exists and unsets `NEO4J_PLUGINS` before calling `/startup/docker-entrypoint.sh`, preventing Neo4j from attempting a `wget` check when Wi-Fi is off.)*

### Step 1.4 — One-time online Wayanad OSM scenario prefetch (T6)
```powershell
uv run python scripts/prefetch_wayanad.py
```
**Expected output:**
```text
Fetching OSM roads and places for Chooralmala/Mundakkai bbox {'south': 11.472, 'north': 11.512, 'west': 76.135, 'east': 76.172}...
Saved Wayanad scenario (scenario reconstructed from reports, not drone-measured) to ...\data\projects\wayanad: {'segments': 1568, 'places': 11}
```

---

## 2. Firewall & Windows Mobile Hotspot Setup (Demo Laptop)

### Step 2.1 — Allow TCP port `8000` on **Private** networks only
Open an **Administrator PowerShell** once and create a rule restricted to `-Profile Private` (never `Public`):
```powershell
New-NetFirewallRule `
  -DisplayName "Vortex Offline Advisor Port 8000 (Private Only)" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 8000 `
  -Profile Private
```
**Expected output:**
```text
Name                  : {GUID}
DisplayName           : Vortex Offline Advisor Port 8000 (Private Only)
Enabled               : True
Profile               : Private
Direction             : Inbound
Action                : Allow
```

### Step 2.2 — Enable Windows Mobile Hotspot (works with Wi-Fi disconnected)
1. Open **Windows Settings → Network & internet → Mobile hotspot**.
2. Set **Share my internet connection** / **Mobile hotspot** to **On** (Band: **2.4 GHz** or **Any available** for maximum phone compatibility).
   - *Note:* If Windows grays out the toggle when Wi-Fi is completely off, turn Wi-Fi **On** without connecting to any router (disconnect from all SSIDs / Airplane-mode upstream off), then toggle **Mobile hotspot → On**. Windows assigns the laptop hotspot adapter `192.168.137.1`.
3. Verify the hotspot adapter profile is **Private** so the firewall rule applies:
   ```powershell
   Get-NetConnectionProfile
   # If the Local Area Connection* hotspot profile shows NetworkCategory : Public, switch it to Private:
   Get-NetConnectionProfile | Where-Object { $_.InterfaceAlias -like "Local Area Connection*" } | Set-NetConnectionProfile -NetworkCategory Private
   ```

---

## 3. Offline Demo Startup Order (Wi-Fi Disconnected)

Disconnect from upstream internet, then run in this exact order:

### Step 3.1 — Verify or restart Neo4j offline
```powershell
docker compose --env-file .env -f neo4j/docker-compose.yml restart
# Neo4j Community on Windows requires 35-45 seconds on startup before accepting Bolt connections:
Start-Sleep -Seconds 45
uv run python -c "from advisor.neo4j_client import open_driver; d = open_driver(timeout_s=10.0); print('GDS:', d.execute_query('RETURN gds.version() AS v').records[0]['v']); d.close()"
```
**Expected output:**
```text
GDS: 2.13.14
```
*(If Docker Desktop is stopped or Neo4j is down, the advisor automatically falls back to `networkx-fallback` with identical JSON output.)*

### Step 3.2 — Load project graph & generate offline reports (CLI check)
```powershell
uv run python -m advisor.load --project wayanad
uv run python -m advisor.report --project wayanad --out data/projects/wayanad/access_report.json
uv run python -m advisor.priorities --project wayanad --out data/projects/wayanad/priorities.json
```
**Expected output:**
```text
loaded project='wayanad' into Neo4j: ... junctions, 1568 segments, 11 places (base=place_WAY_BASE_MEPPADI_APPROACH)
wrote data\projects\wayanad\access_report.json via neo4j-gds (11 places, ... reopen candidates)
wrote data\projects\wayanad\priorities.json (11 priority items, decision_support=True)
```
*(Substitute `--project southfork` once `data/projects/southfork/roads/segments.geojson` and `places.geojson` are generated by the ODM pipeline.)*

### Step 3.3 — Start the FastAPI server (`0.0.0.0:8000`)
```powershell
uv run uvicorn api.main:app --host 0.0.0.0 --port 8000
```
**Expected output:**
```text
WARNING:vortex.api:Optional router 'measure.router' is not available yet; starting API without /measure routes.
WARNING:vortex.api:Optional router 'accuracy.router' is not available yet; starting API without /accuracy routes.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```
*(Once `measure.router`, `accuracy.router`, and `web/dist/` land on `main`, `api.main` mounts them automatically with zero code edits.)*

### Step 3.4 — Print QR code for responder phones (in a second terminal)
```powershell
uv run python scripts/qr.py
```
*(Or pass `--ip 192.168.137.1` explicitly if multiple adapters exist.)*
**Expected output:**
```text
Vortex Field Responder URL: http://192.168.137.1:8000/field
[ASCII QR CODE]
```

---

## 4. Live Demo Verification Checklist

1. **Offline health check** (`http://127.0.0.1:8000/health`):
   - Returns `"status": "ok"`, `"internet_reachable": false`, `"offline_mode": true`.
2. **Phone responder check**:
   - Join a phone (with mobile data **Off**) to the laptop's Windows Mobile Hotspot.
   - Scan the terminal QR code to open `http://192.168.137.1:8000/field`.
   - Confirm the top **freshness line** displays survey time, analysis time, and `Field reports: 0`.
   - Select a blocked place/segment, tap **Cleared** (or **Dead End**), add a short note, and tap **Submit Field Report**.
3. **Immediate advisor & priority update**:
   - Refresh `http://127.0.0.1:8000/advisor/state?project=wayanad` → reported segment now shows `"source": "field_report"` and updated `status_by_mode` + `reasons_by_mode`.
   - Refresh `http://127.0.0.1:8000/advisor/priorities?project=wayanad` → priority ranking updates immediately (`"decision_support": true`).
