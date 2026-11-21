"""Build the submission zip from main, so it matches GitHub exactly.

    uv run python scripts/make_submission_zip.py            # writes ../typhon_submission_<commit>.zip
    uv run python scripts/make_submission_zip.py --out X.zip

It refuses (and says why) when:
  - you are not on main,
  - main has changes that are not committed (they would be missing from the zip),
  - main and GitHub's main differ (push or pull first), so the zip is never something GitHub doesn't have.
Only committed files go in (git archive), so gitignored data, weights and .env files are never included.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", help="zip path (default: next to the repo folder)")
    args = ap.parse_args()

    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if branch != "main":
        print(f"STOP: on branch '{branch}', not main. Run: git checkout main")
        return 1
    dirty = git("status", "--porcelain", "--untracked-files=no")
    if dirty:
        print("STOP: main has uncommitted changes; they would be missing from the zip:\n" + dirty)
        return 1
    git("fetch", "origin", "main")
    local, remote = git("rev-parse", "main"), git("rev-parse", "origin/main")
    if local != remote:
        ahead = git("rev-list", "--count", "origin/main..main")
        behind = git("rev-list", "--count", "main..origin/main")
        print(f"STOP: main differs from GitHub ({ahead} commits not pushed, {behind} not pulled). Push or pull first.")
        return 1

    short = local[:7]
    out = Path(args.out) if args.out else ROOT.parent / f"typhon_submission_{short}.zip"
    git("archive", "--format=zip", f"--prefix={ROOT.name}/", "-o", str(out.resolve()), local)

    with zipfile.ZipFile(out) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
    tracked = git("ls-files").splitlines()
    if len(names) != len(tracked):
        print(f"WARNING: zip has {len(names)} files but git tracks {len(tracked)}")
    print(f"OK: {out.resolve()}")
    print(f"commit {short} (same as GitHub main), {len(names)} files, {out.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
