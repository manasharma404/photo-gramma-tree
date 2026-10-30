# Vortex

hackFront India 2026, PS T8.2 "The First Map After The Landslide": consumer drone footage to a georeferenced map, a change report and field measurements, offline on a laptop.

**Status:** work in progress. Plan, owners and decisions: [PLAN.md](PLAN.md).

## What's real, what's public, what's estimated
Filled in as results arrive. Every number in this project comes from a run we can show, or is labelled `ESTIMATE` or `PLACEHOLDER`.

Draft disclosure: our planned survey flights on 29–30 Oct were cancelled by rain. Accuracy and measurement validation use the USGS South Fork Campground debris-flow survey (public domain), processed without its ground control, plus our own DJI Neo 2 video for the consumer-drone video path.

## Setup (Windows)
Needs Docker Desktop (WSL2), `uv`, ffmpeg and exiftool.

```
uv sync
uv run pytest
```

## Licences and AI disclosure
- Data: [data/LICENSES.md](data/LICENSES.md)
- AI-assisted work: [docs/AI_DISCLOSURE.md](docs/AI_DISCLOSURE.md)
