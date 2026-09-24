from __future__ import annotations

import io
import os
import threading
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from starlette.background import BackgroundTask

WEIGHTS_DIR = Path(os.getenv("FASHN_WEIGHTS_DIR", "weights"))
OUTPUT_DIR = Path(os.getenv("FASHN_OUTPUT_DIR", "outputs"))
WORKER_TOKEN = os.getenv("FASHN_WORKER_TOKEN", "")
DEVICE = os.getenv("FASHN_DEVICE") or None
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000

app = FastAPI(title="Taste Yourself FASHN VTON Worker", version="0.1.0")
_pipeline = None
_pipeline_lock = threading.Lock()
_inference_lock = threading.Lock()


def authenticate(token: str | None) -> None:
    if WORKER_TOKEN and token != WORKER_TOKEN:
        raise HTTPException(status_code=401, detail="invalid_worker_token")


def load_image(raw: bytes) -> Image.Image:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="image_too_large")
    try:
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        with Image.open(io.BytesIO(raw)) as source:
            source.verify()
        with Image.open(io.BytesIO(raw)) as source:
            if source.width * source.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=422, detail="image_dimensions_too_large")
            return source.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise HTTPException(status_code=422, detail="invalid_image") from error


def get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    with _pipeline_lock:
        if _pipeline is None:
            if not WEIGHTS_DIR.is_dir():
                raise HTTPException(status_code=503, detail="weights_not_installed")
            try:
                from fashn_vton import TryOnPipeline
            except ImportError as error:
                raise HTTPException(status_code=503, detail="fashn_vton_not_installed") from error
            _pipeline = TryOnPipeline(weights_dir=str(WEIGHTS_DIR), device=DEVICE)
    return _pipeline


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "weights_present": WEIGHTS_DIR.is_dir(),
        "pipeline_loaded": _pipeline is not None,
    }


@app.post("/v1/try-on", response_class=FileResponse)
async def try_on(
    person: UploadFile = File(),  # noqa: B008
    garment: UploadFile = File(),  # noqa: B008
    category: str = Form(),
    x_worker_token: str | None = Header(default=None),
):
    authenticate(x_worker_token)
    if category not in {"tops", "bottoms", "one-pieces"}:
        raise HTTPException(status_code=422, detail="invalid_category")

    person_image = load_image(await person.read())
    garment_image = load_image(await garment.read())
    pipeline = get_pipeline()
    with _inference_lock:
        result = pipeline(
            person_image=person_image,
            garment_image=garment_image,
            category=category,
            garment_photo_type="flat-lay",
            num_samples=1,
            num_timesteps=30,
            guidance_scale=1.5,
            seed=42,
            segmentation_free=True,
        )

    filename = f"{uuid4()}.jpg"
    output_path = OUTPUT_DIR / filename
    result.images[0].convert("RGB").save(output_path, "JPEG", quality=92)
    return FileResponse(
        output_path,
        media_type="image/jpeg",
        filename=filename,
        background=BackgroundTask(output_path.unlink, missing_ok=True),
    )


@app.get("/outputs/{filename}", response_class=FileResponse)
def output(filename: str):
    target = (OUTPUT_DIR / filename).resolve()
    if OUTPUT_DIR.resolve() not in target.parents or not target.is_file():
        raise HTTPException(status_code=404, detail="output_not_found")
    return FileResponse(target, media_type="image/jpeg")
