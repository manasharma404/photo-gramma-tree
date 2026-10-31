"""Generate terminal and optional PNG QR code for the offline responder /field page (T8).

Usage:
    uv run python scripts/qr.py
    uv run python scripts/qr.py --ip 192.168.137.1 --port 8000 --out data/advisor/field_qr.png
"""
from __future__ import annotations

import argparse
import io
import socket
import sys
from pathlib import Path

import qrcode


def detect_hotspot_or_lan_ip() -> str:
    """Prefer Windows Mobile Hotspot default gateway (192.168.137.x) or private LAN IPv4."""
    candidates: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, family=socket.AF_INET):
            ip = str(info[4][0])
            if ip and not ip.startswith("127.") and not ip.startswith("169.254."):
                candidates.append(ip)
    except OSError:
        pass

    # Windows Mobile Hotspot assigns 192.168.137.1 to the host laptop adapter by default.
    for ip in candidates:
        if ip.startswith("192.168.137."):
            return ip

    # UDP socket route table inspection (does not transmit packets or require internet).
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            routed_ip = str(s.getsockname()[0])
            if routed_ip and not routed_ip.startswith("127."):
                return routed_ip
    except OSError:
        pass

    for ip in candidates:
        if ip.startswith(("192.168.", "10.", "172.")):
            return ip
    return "192.168.137.1"


def build_field_url(ip: str | None = None, port: int = 8000, path: str = "/field") -> str:
    host = ip or detect_hotspot_or_lan_ip()
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"http://{host}:{port}{clean_path}"


def render_qr_ascii(url: str) -> str:
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    buf = io.StringIO()
    qr.print_ascii(out=buf, invert=True)
    return buf.getvalue()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ip", default=None, help="Override laptop hotspot/LAN IPv4 (e.g. 192.168.137.1)")
    ap.add_argument("--port", type=int, default=8000, help="API server port (default: 8000)")
    ap.add_argument("--path", default="/field", help="Target path (default: /field)")
    ap.add_argument("--out", type=Path, default=None, help="Optional PNG path to save QR image")
    args = ap.parse_args(argv)

    url = build_field_url(ip=args.ip, port=args.port, path=args.path)
    ascii_art = render_qr_ascii(url)

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

    print(f"\nVortex Field Responder URL: {url}\n")
    try:
        print(ascii_art)
    except UnicodeEncodeError:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write((ascii_art + "\n").encode("utf-8", errors="replace"))
            sys.stdout.flush()

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        img = qrcode.make(url)
        img.save(args.out)
        print(f"Saved QR PNG to {args.out}")


if __name__ == "__main__":
    main()
