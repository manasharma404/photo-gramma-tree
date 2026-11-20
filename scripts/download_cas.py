"""Download CAS Landslide Dataset (Zenodo record 10294997) UAV subsets.

Licence: CC BY-NC 4.0 / Sichuan Geomatics Center Derivative Works Licence
Subsets used:
  1. Moxi town（UAV-0.2m）.zip (~970 MB, GSD 0.20 m) - Training & Validation
  2. Moxitaidi (UAV-0.6m).zip (~520 MB, GSD 0.60 m) - Held-out Test Region

Total download: ~1.49 GB (avoids downloading the full 9.2 GB satellite/unrelated subsets).
Outputs (under data/cas/, gitignored):
  data/cas/zips/
  data/cas/extracted/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any
import requests

RECORD_ID = "10294997"
ZENODO_API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"

TARGET_SUBSETS = [
    {
        "pattern": "Moxi town",
        "resolution": "0.2m",
        "role": "train_val",
        "gsd_m": 0.20,
        "source": "Sichuan Geomatics Center",
        "licence": "CC BY-NC 4.0 (Derivative Works Licence)",
    },
    {
        "pattern": "Moxitaidi",
        "resolution": "0.6m",
        "role": "held_out_test",
        "gsd_m": 0.60,
        "source": "Sichuan Geomatics Center",
        "licence": "CC BY-NC 4.0 (Derivative Works Licence)",
    },
]


def fetch_zenodo_files() -> list[dict[str, Any]]:
    headers = {"User-Agent": "Typhon-Research/0.1"}
    resp = requests.get(ZENODO_API_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("files", [])


def find_target_files(files: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    matched = []
    for target in TARGET_SUBSETS:
        p = target["pattern"].lower()
        r = target["resolution"].lower()
        for f in files:
            key = f.get("key", "").lower()
            if p in key and r in key and key.endswith(".zip"):
                matched.append((target, f))
                break
    return matched


def download_file(url: str, dest_path: Path, expected_size: int, expected_md5: str | None = None, max_retries: int = 15) -> bool:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    retry = 0
    while retry < max_retries:
        existing_bytes = temp_path.stat().st_size if temp_path.exists() else 0
        if existing_bytes >= expected_size:
            temp_path.replace(dest_path)
            print(f"\nSaved: {dest_path}")
            return True

        headers = {"User-Agent": "Typhon-Research/0.1"}
        if existing_bytes > 0:
            headers["Range"] = f"bytes={existing_bytes}-"
            mode = "ab"
            print(f"Resuming download from byte {existing_bytes} ({existing_bytes / 1e6:.1f} MB)...")
        else:
            mode = "wb"

        try:
            with requests.get(url, headers=headers, stream=True, timeout=60) as resp:
                if resp.status_code not in (200, 206):
                    print(f"Failed download: HTTP {resp.status_code}")
                    retry += 1
                    time.sleep(3)
                    continue

                total_bytes = existing_bytes + int(resp.headers.get("content-length", expected_size - existing_bytes))
                downloaded = existing_bytes

                with open(temp_path, mode) as fp:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            fp.write(chunk)
                            downloaded += len(chunk)
                            pct = (downloaded / total_bytes * 100) if total_bytes else 0
                            print(f"\r  Downloaded: {downloaded / 1e6:.1f} / {total_bytes / 1e6:.1f} MB ({pct:.1f}%)", end="", flush=True)

            print()
            if temp_path.stat().st_size == expected_size:
                temp_path.replace(dest_path)
                print(f"Saved: {dest_path}")
                return True
            else:
                print(f"Partial download ({temp_path.stat().st_size} of {expected_size} bytes). Retrying...")
                retry += 1
                time.sleep(2)
        except Exception as e:
            print(f"\nDownload interrupted ({e}). Retrying in 3 seconds (attempt {retry+1}/{max_retries})...")
            retry += 1
            time.sleep(3)

    print(f"Failed to download after {max_retries} attempts.")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Download CAS Landslide UAV subsets")
    parser.add_argument("--dest", type=Path, default=Path("data/cas"), help="Destination directory")
    parser.add_argument("--dry-run", action="store_true", help="List matched files without downloading")
    args = parser.parse_args()

    print(f"Connecting to Zenodo record {RECORD_ID}...")
    files = fetch_zenodo_files()
    matched = find_target_files(files)

    print(f"Found {len(matched)} target UAV subsets:")
    total_bytes = 0
    for target, f in matched:
        size_mb = f.get("size", 0) / (1024 * 1024)
        total_bytes += f.get("size", 0)
        safe_key = f.get("key", "").encode("ascii", "replace").decode("ascii")
        print(f"  - [{target['role']}] {safe_key}: {size_mb:.1f} MB (GSD: {target['gsd_m']} m)")

    print(f"Total payload size: {total_bytes / 1e6:.1f} MB (~{total_bytes / 1e9:.2f} GB)")

    if args.dry_run:
        print("Dry run complete. No files downloaded.")
        return

    dest_zip_dir = args.dest / "zips"
    for target, f in matched:
        safe_name = f.get("key", "").encode("ascii", "replace").decode("ascii")
        # Normalize non-ascii characters for windows path safety
        ascii_name = f"cas_{target['role']}_{target['resolution']}.zip"
        dest_file = dest_zip_dir / ascii_name
        download_url = f.get("links", {}).get("self")
        if not download_url:
            print(f"No download URL for {safe_name}")
            continue

        if dest_file.exists() and dest_file.stat().st_size == f.get("size", 0):
            print(f"File {dest_file.name} already downloaded ({dest_file.stat().st_size / 1e6:.1f} MB). Skipping.")
            continue

        print(f"\nDownloading {safe_name} to {dest_file.name}...")
        download_file(download_url, dest_file, f.get("size", 0))


if __name__ == "__main__":
    main()
