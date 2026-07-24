import io
import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from PIL import Image
from ultralytics import YOLO

MODEL_PATH = os.environ.get("MODEL_PATH", "best_v2.pt")

app = FastAPI(title="thrashsort API")
model = YOLO(MODEL_PATH)


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_PATH, "classes": model.names}


@app.post("/predict")
async def predict(file: UploadFile = File(...), conf: float = 0.25):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "file must be an image")

    data = await file.read()
    image = Image.open(io.BytesIO(data)).convert("RGB")

    results = model.predict(image, conf=conf, verbose=False)
    result = results[0]

    detections = []
    for box in result.boxes:
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        detections.append({
            "class_id": int(box.cls[0]),
            "class_name": model.names[int(box.cls[0])],
            "confidence": float(box.conf[0]),
            "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        })

    return {"detections": detections, "count": len(detections)}


@app.post("/predict/image")
async def predict_image(file: UploadFile = File(...), conf: float = 0.25):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "file must be an image")

    data = await file.read()
    image = Image.open(io.BytesIO(data)).convert("RGB")

    results = model.predict(image, conf=conf, verbose=False)
    annotated = results[0].plot()  # BGR numpy array

    out = Image.fromarray(annotated[:, :, ::-1])
    buf = io.BytesIO()
    out.save(buf, format="JPEG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <!doctype html>
    <html>
    <head><title>thrashsort test</title></head>
    <body style="font-family: sans-serif; max-width: 640px; margin: 40px auto;">
      <h2>thrashsort model test</h2>
      <form id="f">
        <input type="file" name="file" accept="image/*" required />
        <button type="submit">Detect</button>
      </form>
      <pre id="out"></pre>
      <img id="img" style="max-width: 100%; margin-top: 16px;" />
      <script>
        const f = document.getElementById('f');
        f.addEventListener('submit', async (e) => {
          e.preventDefault();
          const fd = new FormData(f);
          const res = await fetch('/predict', { method: 'POST', body: fd });
          const json = await res.json();
          document.getElementById('out').textContent = JSON.stringify(json, null, 2);

          const res2 = await fetch('/predict/image', { method: 'POST', body: fd });
          const blob = await res2.blob();
          document.getElementById('img').src = URL.createObjectURL(blob);
        });
      </script>
    </body>
    </html>
    """
