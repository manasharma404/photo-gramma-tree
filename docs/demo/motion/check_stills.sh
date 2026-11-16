#!/usr/bin/env bash
# Quick look before a full render: saves frames at the given seconds and tiles them into one sheet.
# Usage (from the repo root):  bash docs/demo/motion/check_stills.sh fallback.html 1.0,2.0,4.9
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
out="$root/docs/demo/motion/out/stills"
mkdir -p "$out"; rm -f "$out"/*.png "$out"/sheet.jpg
(cd "$root/web" && MOTION_SCENE="$1" node scripts/motion_render.mjs "$out/fb.mp4" "$2")
i=0
for f in $(ls "$out"/fb_*.png | sort -t_ -k2 -n); do cp "$f" "$out/$(printf 'n%03d.png' $i)"; i=$((i + 1)); done
rows=$(( (i + 2) / 3 ))
ffmpeg -y -loglevel error -i "$out/n%03d.png" -vf "scale=640:-1,tile=3x${rows}:padding=6:color=white" -frames:v 1 "$out/sheet.jpg"
echo "sheet: $out/sheet.jpg ($i frames)"
