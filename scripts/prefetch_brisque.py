"""Prefetch OpenCV QualityBRISQUE SVR model/range YAML files for M1 / T13 evaluation.

Run ONCE while online:
    uv run python scripts/prefetch_brisque.py

Outputs (under data/models/brisque/, gitignored):
    - brisque_model_live.yml (Apache-2.0 / BSD-2-Clause LIVE IQA SVR weights)
    - brisque_range_live.yml
"""
from __future__ import annotations

import argparse
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent

BRISQUE_FILES = {
    "brisque_model_live.yml": (
        "https://raw.githubusercontent.com/opencv/opencv_contrib/4.x/"
        "modules/quality/samples/brisque_model_live.yml"
    ),
    "brisque_range_live.yml": (
        "https://raw.githubusercontent.com/opencv/opencv_contrib/4.x/"
        "modules/quality/samples/brisque_range_live.yml"
    ),
}

HTTP_HEADERS = {
    "User-Agent": "Vortex-T8.2-Prototype/0.1 (hackFront India 2026 offline landslide advisor; academic research)",
}


def prefetch_brisque(out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for fname, url in BRISQUE_FILES.items():
        dst = out_dir / fname
        resp = requests.get(url, headers=HTTP_HEADERS, timeout=45)
        resp.raise_for_status()
        dst.write_bytes(resp.content)
        written[fname] = dst
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "data" / "models" / "brisque",
        help="Destination folder for OpenCV BRISQUE YAML files",
    )
    args = ap.parse_args()
    written = prefetch_brisque(args.out_dir)
    for fname, path in written.items():
        print(f"Downloaded {fname} ({path.stat().st_size} bytes) -> {path}")


if __name__ == "__main__":
    main()
