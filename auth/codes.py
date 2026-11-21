"""Create or show the access codes (kept in the git-ignored .env, never in the repo or in chat).

    uv run python -m auth.codes            # show the codes, creating any that are missing
    uv run python -m auth.codes --new      # replace all codes (everyone signs in again)

Prints them in YOUR terminal only, to write on the cards for judges and field teams.
"""
from __future__ import annotations

import argparse

from auth import core

KEYS = ("VORTEX_OPERATOR_CODE", "VORTEX_EVALUATOR_CODE", "VORTEX_TEAM_PINS", "VORTEX_SESSION_SECRET")


def ensure(replace: bool = False) -> list[str]:
    """add missing codes to .env (or replace them); returns the names written"""
    path = core.ROOT / ".env"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    present = {ln.split("=", 1)[0].strip() for ln in lines if "=" in ln and not ln.lstrip().startswith("#")}
    fresh = {
        "VORTEX_OPERATOR_CODE": core.new_code(),
        "VORTEX_EVALUATOR_CODE": core.new_code(),
        "VORTEX_TEAM_PINS": ",".join(f"Team {t}:{core.new_code(6)}" for t in "ABC"),
        "VORTEX_SESSION_SECRET": core.new_code() + core.new_code(),
    }
    written = []
    if replace:
        lines = [ln for ln in lines if ln.split("=", 1)[0].strip() not in KEYS]
        present -= set(KEYS)
    for k in KEYS:
        if k not in present:
            lines.append(f"{k}={fresh[k]}")
            written.append(k)
    if written:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", action="store_true", help="replace every code")
    a = ap.parse_args()
    written = ensure(replace=a.new)
    if written:
        print("Created in .env:", ", ".join(written))
    s = core._settings()
    print("Operator (laptop):  ", s["VORTEX_OPERATOR_CODE"])
    print("Evaluator (judges): ", s["VORTEX_EVALUATOR_CODE"])
    for name, pin in core.teams().items():
        print(f"{name + ' (phone):':20}", pin)
    print("Sign in at http://<laptop-ip>:8000/login")


if __name__ == "__main__":
    main()
