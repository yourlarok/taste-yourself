from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MIN_IMAGE_SIDE = 128
MAX_IMAGE_SIDE = 8192
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class InvalidImage(ValueError):
    pass


@dataclass(frozen=True)
class StoredImage:
    relative_path: str
    width: int
    height: int


class LocalImageStorage:
    """Development storage that normalizes images and strips embedded metadata."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, upload: UploadFile, namespace: str) -> StoredImage:
        if upload.content_type not in ALLOWED_CONTENT_TYPES:
            raise InvalidImage("unsupported_image_type")

        raw = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(raw) > MAX_UPLOAD_BYTES:
            raise InvalidImage("image_too_large")

        try:
            Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
            with Image.open(io.BytesIO(raw)) as source:
                source.verify()
            with Image.open(io.BytesIO(raw)) as source:
                width, height = source.size
                if min(width, height) < MIN_IMAGE_SIDE:
                    raise InvalidImage("image_too_small")
                if max(width, height) > MAX_IMAGE_SIDE or width * height > MAX_IMAGE_PIXELS:
                    raise InvalidImage("image_dimensions_too_large")
                normalized = source.convert("RGB")
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            raise InvalidImage("invalid_image") from error

        folder = self.root / namespace
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4()}.jpg"
        destination = (folder / filename).resolve()
        if self.root not in destination.parents:
            raise InvalidImage("invalid_storage_path")
        normalized.save(destination, format="JPEG", quality=90, optimize=True)
        return StoredImage(
            relative_path=f"{namespace}/{filename}",
            width=width,
            height=height,
        )

    def save_generated(self, raw: bytes, namespace: str = "results") -> StoredImage:
        try:
            with Image.open(io.BytesIO(raw)) as source:
                width, height = source.size
                normalized = source.convert("RGB")
        except (UnidentifiedImageError, OSError) as error:
            raise InvalidImage("invalid_generated_image") from error

        folder = self.root / namespace
        folder.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4()}.jpg"
        destination = (folder / filename).resolve()
        if self.root not in destination.parents:
            raise InvalidImage("invalid_storage_path")
        normalized.save(destination, format="JPEG", quality=92, optimize=True)
        return StoredImage(
            relative_path=f"{namespace}/{filename}",
            width=width,
            height=height,
        )

    def delete(self, relative_path: str) -> bool:
        target = (self.root / relative_path).resolve()
        if self.root not in target.parents or not target.is_file():
            return False
        target.unlink()
        return True
