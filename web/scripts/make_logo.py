"""Derive UI logo files from the lead's SVGs (white, for dark backgrounds) -> currentColor versions.

    uv run python web/scripts/make_logo.py "<Frame 1229.svg>" "<Frame 1230.svg>"

Writes web/src/assets/logo-mark.svg (icon), logo-lockup.svg (TYPH + mark + N) and
logo-full.svg (PROJECT over the lockup), plus web/public/favicon.svg.
The mark's last path (the mountain) is a cut-out: it takes the background colour.
"""
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent
paths = lambda f: re.findall(r'<path d="([^"]+)"', Path(f).read_text(encoding="utf-8"))

mark, word = paths(sys.argv[1]), paths(sys.argv[2])
project_text, big_letters = word[0], word[1]

splash = "".join(f'<path d="{d}" fill="currentColor"/>' for d in mark[:-1])
cutout = f'<path d="{mark[-1]}" fill="var(--logo-cutout, #F8F6EF)"/>'
mark_body = splash + cutout

# mark artwork spans x 95..601, y 196..491 in its 697x697 frame; the O gap in the wordmark is x 1354..1794, y 175..391
scale = (391 - 175) / (491 - 196)
x0 = (1354 + 1794) / 2 - (601 - 95) * scale / 2
in_o = f'<g transform="translate({x0:.1f},175) scale({scale:.4f}) translate(-95,-196)">{mark_body}</g>'

out = WEB / "src" / "assets"
out.mkdir(parents=True, exist_ok=True)
svg = lambda vb, body, label: (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" role="img" aria-label="{label}">'
                               f"<title>{label}</title>{body}</svg>\n")
(out / "logo-mark.svg").write_text(svg("90 190 517 306", mark_body, "Project Typhon"), encoding="utf-8")
(out / "logo-lockup.svg").write_text(svg("118 171 1960 224", f'<path d="{big_letters}" fill="currentColor"/>' + in_o, "Typhon"), encoding="utf-8")
(out / "logo-full.svg").write_text(svg("110 60 1970 336", f'<path d="{project_text}" fill="currentColor"/><path d="{big_letters}" fill="currentColor"/>' + in_o,
                                       "Project Typhon"), encoding="utf-8")
fav = mark_body.replace('fill="currentColor"', 'fill="#2F3E2E"').replace("var(--logo-cutout, #F8F6EF)", "#F8F6EF")
(WEB / "public" / "favicon.svg").write_text(svg("90 190 517 306", fav, "Project Typhon"), encoding="utf-8")
print("wrote", [p.name for p in out.glob("logo-*.svg")], "and public/favicon.svg")
