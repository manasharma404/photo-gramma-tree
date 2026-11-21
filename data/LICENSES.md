# Data licences

Every external dataset we use. Public data is labelled as public in the UI and never presented as our footage.

| Dataset | Source | Licence | Retrieved | What we use it for |
|---|---|---|---|---|
| DJI Neo 2 videos 0148, 0149 (20 Aug 2026) | Our own footage | Ours | 31 Oct 2026 | Video-to-map path; "what responders have today" |
| USGS South Fork Campground debris flow, aerial images `F01-5`, `F02-2` (flown 30 Apr 2024) | USGS data release doi:10.5066/P144KDGN, ScienceBase item 67353631d34e6fbce7b5d58f (downloaded by hand: ScienceBase blocks scripts) | Public domain (US Government work); credit USGS | 31 Oct 2026 | Processing benchmark and accuracy validation; **public data, never presented as our footage** |
| USGS South Fork RTK GNSS points (`SEKI_SouthFork_DebrisFlow_2024_RTK_GNSS.csv`: 18 AT + 5 CHLK targets, 1576 TOPO, 1 BASE) | Same data release, ScienceBase item 6735365ad34e6fbce7b5d592; metadata `SEKI_SouthFork_DebrisFlow_GNSS_metadata.xml` (states NAD83(2011), NAVD88/GEOID18) | Public domain; credit USGS | 31 Oct 2026 | Independent checkpoints (never used as GCPs) and height comparison |
| OpenStreetMap roads and tracks around South Fork (`data/prefetch/osm_southfork.gpkg`) | OpenStreetMap via the Overpass API, fetched once by `scripts/prefetch_osm_southfork.py` (no internet at runtime) | ODbL 1.0; credit "© OpenStreetMap contributors" (shown on the map) | 31 Oct 2026 | Road centrelines that we check against the map |
| USGS 1 m terrain model from lidar, tile `USGS_1M_11_x34y403_CA_SierraNevada_B22.tif` (310 MB, `data/prefetch/usgs_1m/`, SHA-256 `698855f5…c8ec7e2`); lidar flown **3 Nov 2021 to 23 Sep 2022**, before the debris flow of 9 Jan 2023 | USGS 3D Elevation Program, found through the National Map catalogue; dates from the tile's metadata file | Public domain (US Government work); USGS asks for credit and that changes we make are described | 16 Nov 2026 | Terrain from before the slide, to compare with our height model (planned for the finale; not used in any result yet) |
| OpenStreetMap roads and places for Nepal flood corridor (`data/projects/nepal/`) | OpenStreetMap contributors (via `scripts/prefetch_nepal.py`) | ODbL 1.0; credit "© OpenStreetMap contributors" | 17 Nov 2026 | Road network geometry and facility locations for the 26 Aug 2026 Nepal flash flood scenario |
| Nepal National Population and Housing Census 2021 | National Statistics Office, Government of Nepal | Government of Nepal Open Data | 17 Nov 2026 | Cited settlement populations for the Trishuli-Prithvi corridor |
| Copernicus DEM GLO-30 Public, 4 tiles N27–N28 E084–E085 (about 170 MB, `data/prefetch/copernicus_nepal/`). A **surface** model (includes trees and buildings), 30 m; collected 2011–2015, so it predates the 26 Aug 2026 flood | Free public copy on AWS open data (`copernicus-dem-30m` bucket), fetched by `scripts/prefetch_nepal_terrain.py` | Copernicus DEM licence (free, with credit), linked from the bucket's readme. Credit: "© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved" (standard wording; confirm on the licence page before the final submission) | 21 Nov 2026 | Offline shaded-relief base map and 3D terrain for the Nepal corridor; context only, too coarse to measure a slide |
| CAS Landslide Dataset: Moxi town (UAV-0.2 m, 1,635 images, GSD 0.20 m) | Sichuan Geomatics Center via Zenodo 10294997 (Xu et al., Scientific Data 2024) | CC BY-NC 4.0 (Derivative Works Licence) | 17 Nov 2026 | Training/val set for drone debris segmentation model (T1) |
| CAS Landslide Dataset: Moxitaidi (UAV-0.6 m, 984 images, GSD 0.60 m) | Sichuan Geomatics Center via Zenodo 10294997 (Xu et al., Scientific Data 2024) | CC BY-NC 4.0 (Derivative Works Licence) | 17 Nov 2026 | Held-out test region for drone debris segmentation model (T1) |

## Demo video audio

| Item | Source | Licence | Used for |
|---|---|---|---|
| "WIN AGAIN" (free type beat) | Truckky Beats, YouTube | Free-download beat; terms not checked beyond the title ("FREE"). Credit: **prod. Truckky Beats**. Non-commercial hackathon use only | Background music under the voiceover in the final demo video (not in this repo) |

Add any other dataset here when it is downloaded.
