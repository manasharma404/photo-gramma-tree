"""Unit tests for the telemetry decoder and the frame quality check (no video needed)."""
import struct

import numpy as np

from pipeline import dji_telemetry, frame_quality


def _key(field, wire):
    return bytes([(field << 3) | wire])


def _msg(field, payload):
    return _key(field, 2) + bytes([len(payload)]) + payload


def _varint(field, value):
    out = bytearray(_key(field, 0))
    while True:
        b = value & 0x7F
        value >>= 7
        out.append(b | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _double(field, value):
    return _key(field, 1) + struct.pack("<d", value)


def make_packet(frame, time_us, lat, lon, alt_mm):
    # Same nesting as the Neo 2: 3 { 1 {1: frame, 2: time} 4 { 4 { 1 {2: lat, 3: lon} 2: alt } } }
    # frame=None leaves the counter out, as protobuf does for the default value 0
    pos = _msg(1, _double(2, lat) + _double(3, lon)) + _varint(2, alt_mm)
    header = (b"" if frame is None else _varint(1, frame)) + _varint(2, time_us)
    body = _msg(1, header) + _msg(4, _msg(4, pos))
    return _msg(3, body)


def test_frame_record_reads_known_fields():
    rec = dji_telemetry.frame_record(make_packet(30, 1_000_000, 12.5, 76.25, 301_785))
    assert rec["frame_index"] == 30
    assert rec["time_us"] == 1_000_000
    assert rec["lat"] == 12.5 and rec["lon"] == 76.25
    assert rec["alt_raw_mm"] == 301_785
    assert rec["iso"] is None


def test_frame_zero_has_index_zero():
    # protobuf omits default values, so frame 0 has no frame_index field
    rec = dji_telemetry.frame_record(make_packet(None, 5, 1.0, 2.0, 3))
    assert rec["time_us"] == 5
    assert rec["frame_index"] == 0


def test_decode_rejects_garbage():
    assert dji_telemetry.decode(b"\x07\x00\x00") is None


def test_measure_flat_vs_textured():
    flat = np.full((64, 64), 10, np.uint8)
    checker = (np.indices((64, 64)).sum(axis=0) % 2 * 255).astype(np.uint8)
    f, c = frame_quality.measure(flat), frame_quality.measure(checker)
    assert f["mean_luma"] == 10 and f["laplacian_var"] == 0
    assert c["laplacian_var"] > 1000
