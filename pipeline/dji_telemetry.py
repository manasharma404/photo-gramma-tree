"""Read the per-frame GPS track that the DJI Neo 2 stores inside its MP4.

The Neo 2 writes one protobuf message per video frame into a data stream named
"CAM meta" (protocol "dvtm_NEO2.proto"). DJI does not publish that layout and
exiftool 13.59 does not decode it, so we decode the protobuf wire format
generically and pick fields by path. The field meanings below were inferred on
31 Oct 2026 from value ranges in our own clips; see FIELDS.
"""
import json
import struct
import subprocess
from collections import defaultdict

# path -> (name, meaning, confidence). Paths are protobuf field numbers joined by ".".
FIELDS = {
    "3.1.1": ("frame_index", "frame counter; absent on frame 0 (protobuf default)", "high"),
    "3.1.2": ("time_us", "timestamp in microseconds", "high"),
    "3.4.4.1.2": ("lat", "latitude, degrees (double)", "high"),
    "3.4.4.1.3": ("lon", "longitude, degrees (double)", "high"),
    "3.4.4.2": ("alt_raw_mm", "altitude in mm; reference (MSL, ellipsoid or barometric) unknown", "low"),
    "3.2.3.1": ("iso", "sensor ISO (float); inferred from 490-4180 range at night", "medium"),
}


def _varint(b, i):
    result = shift = 0
    while True:
        c = b[i]
        i += 1
        result |= (c & 0x7F) << shift
        shift += 7
        if not c & 0x80:
            return result, i


def decode(buf, path="", out=None, depth=0):
    """Decode protobuf bytes into {path: [values]}. Returns None if buf is not a valid message."""
    out = defaultdict(list) if out is None else out
    i = 0
    try:
        while i < len(buf):
            key, i = _varint(buf, i)
            field, wire = key >> 3, key & 7
            if field == 0:
                return None
            p = f"{path}.{field}" if path else str(field)
            if wire == 0:
                v, i = _varint(buf, i)
                out[p].append(v)
            elif wire == 1:
                out[p].append(struct.unpack_from("<d", buf, i)[0])
                i += 8
            elif wire == 5:
                out[p].append(struct.unpack_from("<f", buf, i)[0])
                i += 4
            elif wire == 2:
                n, i = _varint(buf, i)
                if i + n > len(buf):
                    return None
                sub = buf[i:i + n]
                i += n
                nested = defaultdict(list)
                if n and depth < 8 and decode(sub, p, nested, depth + 1) is not None:
                    for k, v in nested.items():
                        out[k].extend(v)
                else:
                    out[p].append(bytes(sub))
            else:
                return None
    except (IndexError, struct.error):
        return None
    return out


def frame_record(packet):
    """One frame's telemetry as a flat dict of the known FIELDS (missing -> None)."""
    fields = decode(packet) or {}
    rec = {name: (fields[path][0] if fields.get(path) else None) for path, (name, _, _) in FIELDS.items()}
    if rec["frame_index"] is None and rec["time_us"] is not None:
        rec["frame_index"] = 0
    return rec


def read_packets(video, stream_index=1):
    """Split the telemetry data stream into per-frame packets using ffprobe packet sizes."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", str(stream_index),
         "-show_entries", "packet=size", "-of", "json", str(video)],
        capture_output=True, check=True)
    sizes = [int(p["size"]) for p in json.loads(probe.stdout)["packets"]]
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), "-map", f"0:{stream_index}", "-c", "copy", "-f", "data", "-"],
        capture_output=True, check=True).stdout
    if sum(sizes) != len(raw):
        raise ValueError(f"packet sizes ({sum(sizes)}) do not match stream bytes ({len(raw)})")
    packets, off = [], 0
    for s in sizes:
        packets.append(raw[off:off + s])
        off += s
    return packets


def read_track(video):
    """Per-frame telemetry records for a Neo 2 MP4."""
    return [frame_record(p) for p in read_packets(video)]
