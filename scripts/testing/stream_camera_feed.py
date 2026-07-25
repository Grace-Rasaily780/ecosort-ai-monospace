#!/usr/bin/env python3
"""
Reads the ESP32-CAM feed relayed through the devkit's UART bridge and
serves it as an MJPEG stream over HTTP (looks like live video in a browser).
Saves each frame to disk briefly, then deletes older ones as new ones arrive
(only keeps the most recent few, to avoid piling up files).

Usage:
    python3 stream_camera_feed.py [port] [baud] [http_port]

Defaults: port=/dev/ttyUSB0  baud=115200  http_port=8080

Open http://<this-machine-ip>:8080/ in a browser to view.
Press Ctrl+C to stop.
"""

import serial
import sys
import os
import glob
import threading
import time
import requests
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
BAUD = int(sys.argv[2]) if len(sys.argv) > 2 else 115200
HTTP_PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8080

OUTPUT_DIR = "./frames_live"
KEEP_LAST = 2  # how many recent frame files to keep on disk

DETECT_URL = "http://localhost:8000/predict"
DETECT_INTERVAL = 2.0  # seconds between detection calls, to avoid hammering the API

CLASS_TO_CMD = {
    "Bio-degradable": b"B",
    "Non-Biodegradable": b"N",
    "E-Waste": b"E",
}

SOI = b"\xff\xd8"
EOI = b"\xff\xd9"
MAX_JUNK = 200_000

latest_frame = None
latest_lock = threading.Lock()
frame_count = 0
stop_event = threading.Event()
detection_busy = threading.Lock()


def run_detection(ser, frame):
    if not detection_busy.acquire(blocking=False):
        return  # previous detection still in flight, skip this frame
    try:
        files = {"file": ("frame.jpg", frame, "image/jpeg")}
        resp = requests.post(DETECT_URL, files=files, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"detection request failed: {e}")
        return
    finally:
        detection_busy.release()

    if data["count"] == 0:
        print("nothing detected")
        return

    best = max(data["detections"], key=lambda d: d["confidence"])
    cmd = CLASS_TO_CMD.get(best["class_name"])
    print(f"detected: {best['class_name']} ({best['confidence']:.2f})")
    if cmd:
        ser.write(cmd)


def reader_thread():
    global latest_frame, frame_count
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ser = serial.Serial(PORT, BAUD, timeout=1)
    buf = bytearray()
    last_detect = 0.0

    while not stop_event.is_set():
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

        path = os.path.join(OUTPUT_DIR, f"frame_{frame_count:05d}.jpg")
        with open(path, "wb") as f:
            f.write(frame)

        with latest_lock:
            latest_frame = frame
        frame_count += 1

        now = time.time()
        if now - last_detect >= DETECT_INTERVAL:
            last_detect = now
            threading.Thread(target=run_detection, args=(ser, frame), daemon=True).start()

        # delete older frame files, keep only the last KEEP_LAST
        files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "frame_*.jpg")))
        for old in files[:-KEEP_LAST]:
            try:
                os.remove(old)
            except OSError:
                pass

    ser.close()


class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # quiet

    def do_GET(self):
        if self.path == "/stream":
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header(
                "Content-Type", "multipart/x-mixed-replace; boundary=frame"
            )
            self.end_headers()
            try:
                last_sent = None
                while not stop_event.is_set():
                    with latest_lock:
                        frame = latest_frame
                    if frame is not None and frame is not last_sent:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                        last_sent = frame
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><body style='margin:0;background:#000'>"
                b"<img src='/stream' style='width:100%;display:block'>"
                b"</body></html>"
            )


def main():
    t = threading.Thread(target=reader_thread, daemon=True)
    t.start()

    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), StreamHandler)
    print(f"Streaming at http://0.0.0.0:{HTTP_PORT}/  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.shutdown()
        print(f"\nStopped. {frame_count} frames processed.")


if __name__ == "__main__":
    main()
