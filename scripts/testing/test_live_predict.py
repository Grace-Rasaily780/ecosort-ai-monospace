#!/usr/bin/env python3
"""
End-to-end pipeline test: reads live JPEG frames off the devkit UART bridge
(/dev/ttyUSB0), POSTs each to the thrashsort-api /predict endpoint, prints the
classification, and writes the matching single-byte command back down the
same serial link so the CAM board's firmware (esp32cam_firmware.ino) blinks
the right LED.

Usage:
    python3 test_live_predict.py [port] [baud] [server_url]

Defaults: port=/dev/ttyUSB0  baud=115200  server_url=http://localhost:8000/predict
"""

import sys
import threading
import time
import serial
import requests

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
SERVER_URL = sys.argv[3] if len(sys.argv) > 3 else "https://monospace.rootictech.com/predict"

DETECT_INTERVAL = 2.0  # seconds between predict calls, avoid hammering the API

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
MAX_JUNK = 200_000

CLASS_TO_CMD = {
    "Bio-degradable": b"B",
    "Non-Biodegradable": b"N",
    "E-Waste": b"E",
}


predict_busy = threading.Lock()


def run_predict(ser, frame):
    if not predict_busy.acquire(blocking=False):
        return  # previous predict still in flight, skip this frame
    try:
        files = {"file": ("frame.jpg", frame, "image/jpeg")}
        resp = requests.post(SERVER_URL, files=files, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"predict request failed: {e}")
        return
    finally:
        predict_busy.release()

    if data["count"] == 0:
        print(f"{time.strftime('%H:%M:%S')} nothing detected")
        return

    best = max(data["detections"], key=lambda d: d["confidence"])
    cmd = CLASS_TO_CMD.get(best["class_name"])
    print(f"{time.strftime('%H:%M:%S')} {best['class_name']} ({best['confidence']:.2f}) -> cmd {cmd}")
    if cmd:
        ser.write(cmd)
    else:
        print(f"  warning: no LED command mapped for class {best['class_name']!r}")


def main():
    print(f"reading {PORT} @ {BAUD} baud, POSTing to {SERVER_URL}")
    ser = serial.Serial(PORT, BAUD, timeout=1)
    buf = bytearray()
    last_predict = 0.0

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

            now = time.time()
            if now - last_predict >= DETECT_INTERVAL:
                last_predict = now
                threading.Thread(target=run_predict, args=(ser, frame), daemon=True).start()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
