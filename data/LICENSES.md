# Data licences

Every external dataset we use. Public data is labelled as public in the UI and never presented as our footage.

| Dataset | Source | Licence | Retrieved | What we use it for |
|---|---|---|---|---|
| DJI Neo 2 videos 0148, 0149 (20 Aug 2026) | Our own footage | Ours | 31 Oct 2026 | Video-to-map path; "what responders have today" |
| USGS South Fork Campground debris flow, aerial images `F01-5`, `F02-2` (flown 30 Apr 2024) | USGS data release doi:10.5066/P144KDGN, ScienceBase item 67353631d34e6fbce7b5d58f (downloaded by hand: ScienceBase blocks scripts) | Public domain (US Government work); credit USGS | 31 Oct 2026 | Processing benchmark and accuracy validation; **public data, never presented as our footage** |
| USGS South Fork RTK GNSS points (`SEKI_SouthFork_DebrisFlow_2024_RTK_GNSS.csv`: 18 AT + 5 CHLK targets, 1576 TOPO, 1 BASE) | Same data release, ScienceBase item 6735365ad34e6fbce7b5d592 | Public domain; credit USGS | 31 Oct 2026 | Independent checkpoints (never used as GCPs) and height comparison |
| OpenStreetMap roads and tracks around South Fork (`data/prefetch/osm_southfork.gpkg`) | OpenStreetMap via the Overpass API, fetched once by `scripts/prefetch_osm_southfork.py` (no internet at runtime) | ODbL 1.0; credit "© OpenStreetMap contributors" (shown on the map) | 31 Oct 2026 | Road centrelines that we check against the map |

Add any other dataset here when it is downloaded.
