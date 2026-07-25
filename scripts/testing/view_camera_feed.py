#!/usr/bin/env python3
"""
Reads the ESP32-CAM feed relayed through the devkit's UART bridge (via
/dev/ttyUSB0) and saves each JPEG frame to disk as it arrives.

Usage:
    python3 view_camera_feed.py [output_dir] [port] [baud]

Defaults: output_dir=./frames  port=/dev/ttyUSB0  baud=115200

Press Ctrl+C to stop.
"""

import serial
import sys
import os
import time

OUTPUT_DIR = sys.argv[1] if len(sys.argv) > 1 else "./frames"
PORT = sys.argv[2] if len(sys.argv) > 2 else "/dev/ttyUSB0"
BAUD = int(sys.argv[3]) if len(sys.argv) > 3 else 115200

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
MAX_JUNK = 200_000  # drop buffer if no SOI found within this many bytes


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ser = serial.Serial(PORT, BAUD, timeout=1)

    buf = bytearray()
    count = 0
    print(f"Listening on {PORT} @ {BAUD} baud, saving frames to {OUTPUT_DIR}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            chunk = ser.read(512)
            if chunk:
                buf.extend(chunk)

            soi = buf.find(SOI)
            if soi == -1:
                if len(buf) > MAX_JUNK:
                    buf.clear()
                continue

            eoi = buf.find(EOI, soi + 2)
            if eoi == -1:
                if soi > 0:
                    del buf[:soi]
                continue

            frame = bytes(buf[soi:eoi + 2])
            del buf[:eoi + 2]

            path = os.path.join(OUTPUT_DIR, f"frame_{count:05d}.jpg")
            with open(path, "wb") as f:
                f.write(frame)

            print(f"[{time.strftime('%H:%M:%S')}] saved {path} ({len(frame)} bytes)")
            count += 1

    except KeyboardInterrupt:
        print(f"\nStopped. {count} frames saved to {OUTPUT_DIR}")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
