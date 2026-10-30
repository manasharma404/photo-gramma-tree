"""Standard brightness and sharpness check for photos and video frames.

This is a plain image measurement, not a model: mean luminance and variance of
the Laplacian. The teammate's ML model (image_quality.json, method "ml_model")
replaces it when ready; until then outputs say method "standard_check".
"""
import subprocess

import cv2
import numpy as np


def measure(gray):
    """Mean luminance (0-255) and Laplacian variance of a single-channel uint8 image."""
    return {
        "mean_luma": float(gray.mean()),
        "laplacian_var": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
    }


def video_frame_gray(video, t_seconds, width, height):
    """Decode one frame at full resolution as grayscale via ffmpeg (handles HEVC 4K)."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t_seconds:.3f}", "-i", str(video), "-map", "0:0",
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True, check=True).stdout
    if len(raw) != width * height:
        raise ValueError(f"expected {width * height} bytes at t={t_seconds}, got {len(raw)}")
    return np.frombuffer(raw, np.uint8).reshape(height, width)
