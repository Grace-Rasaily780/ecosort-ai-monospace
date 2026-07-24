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
