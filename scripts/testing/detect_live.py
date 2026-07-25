#!/usr/bin/env python3
"""
Watches ./frames_live for new JPEG frames (produced by stream_camera_feed.py
or view_camera_feed.py reading the ESP32-CAM via the devkit UART bridge) and
POSTs each new one to the thrashsort FastAPI server for detection.

Usage:
    python3 detect_live.py [frames_dir] [server_url]

Defaults: frames_dir=./frames_live  server_url=http://localhost:8000/predict
"""

import sys
import os
import time
import glob
import requests

FRAMES_DIR = sys.argv[1] if len(sys.argv) > 1 else "./frames_live"
SERVER_URL = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000/predict"

seen = set()


def main():
    print(f"watching {FRAMES_DIR} -> POST {SERVER_URL}")
    while True:
        frames = sorted(glob.glob(os.path.join(FRAMES_DIR, "*.jpg")))
        new = [f for f in frames if f not in seen]

        for path in new:
            seen.add(path)
            try:
                with open(path, "rb") as f:
                    files = {"file": (os.path.basename(path), f, "image/jpeg")}
                    resp = requests.post(SERVER_URL, files=files, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"{os.path.basename(path)}: request failed ({e})")
                continue

            if data["count"] == 0:
                print(f"{os.path.basename(path)}: nothing detected")
                continue

            best = max(data["detections"], key=lambda d: d["confidence"])
            print(f"{os.path.basename(path)}: {best['class_name']} ({best['confidence']:.2f})")

        # keep 'seen' bounded, frames_live only retains last few files anyway
        if len(seen) > 200:
            seen.clear()

        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
