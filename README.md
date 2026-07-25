# thrashsort-api

FastAPI wrapper serving `best_v2.pt` (ultralytics YOLO) for testing.

## Run (local)

```
./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 for browser test UI, or use endpoints directly:

- `GET /health` — model status + class names
- `POST /predict` — multipart image upload, returns JSON detections
- `POST /predict/image` — multipart image upload, returns annotated JPEG

Model path defaults to `best_v2.pt` (same dir), override with `MODEL_PATH` env var.

## Run (VPS deployment)

```
docker compose up -d --build
```

Nginx reverse-proxies to the `api` container internally on 8000, exposed on the host at **8334**. Open `http://<vps-host>:8334/`.

## Model training

`EcoSort AI.ipynb` — Colab notebook that fine-tunes `yolo11s.pt` on a 3-class
dataset (`Bio-degradable`, `Non-Biodegradable`, `E-Waste`) to produce
`best_v2.pt`.

## ESP32-CAM pipeline

`esp32cam_client/`:

- `esp32cam_firmware.ino` — runs on the ESP32-CAM. Streams JPEG frames out
  over hardware UART2 (GPIO14/15).
- `esp32cam_client_bridge.ino` — runs on a second devkit wired to the CAM's
  UART2 (GPIO16/17). Reassembles JPEG frames from the serial stream, POSTs
  each directly to the hosted `/predict` endpoint over WiFi/HTTP (no PC in
  the loop), and drives two LEDs off the response:
  - GPIO12 (green) = Bio-degradable
  - GPIO13 (red) = Non-Biodegradable
  - both = E-waste

  Also relays the raw byte stream out over USB for optional PC-side viewing
  and accepts manual `'B'`/`'N'`/`'E'` bytes from the serial monitor to test
  the LEDs directly. Requires the ArduinoJson library (v6+).

  Originally POSTed to the raw nginx port (`:8334`) directly; switched to
  going through the Caddy-fronted hostname on plain `http://` (no TLS
  handshake, `:8334` firewalled externally, port 80 open) — see commit
  "https -> http transform".
