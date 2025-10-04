"""Utilities for working with images extracted from PDFs."""
from __future__ import annotations

import base64
import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, UnidentifiedImageError

from .pdf_extractor import ExtractedImage

logger = logging.getLogger(__name__)


@dataclass
class ImageAssetPreparation:
    """Result from preparing an image for downstream consumption."""

    file_path: Path
    data_url: str
    mime_type: str


def select_best_image(images: Iterable[ExtractedImage]) -> Optional[ExtractedImage]:
    """Return the largest image by byte size from *images*.

    For many PDFs das größte Bild entspricht dem Food-Foto; Icons/Logos sind in der
    Regel deutlich kleiner.
    """

    images = list(images)
    if not images:
        return None

    return max(images, key=lambda img: len(img.data))


def prepare_image_asset(
    image_bytes: bytes,
    *,
    base_name: str,
    output_dir: Path,
    prefer_extension: str = "jpg",
) -> Optional[ImageAssetPreparation]:
    """Convert *image* into a JPEG file and corresponding data URL.

    Writes the normalized JPEG to *output_dir* (creating directories as needed) and
    returns metadata required for the Mealie upload. Falls back to PNG, wenn die
    Konvertierung in JPEG fehlschlägt.
    """

    output_dir.mkdir(parents=True, exist_ok=True)

    stem = _slugify(base_name) or "image"

    for extension in (prefer_extension, "png"):
        try:
            result = _convert_and_save(image_bytes, output_dir, stem, extension)
        except UnidentifiedImageError as exc:
            logger.warning("Bild konnte nicht interpretiert werden: %s", exc)
            return None
        if result is not None:
            return result

    return None


def _convert_and_save(data: bytes, directory: Path, stem: str, extension: str) -> Optional[ImageAssetPreparation]:
    image_format = "JPEG" if extension.lower() in {"jpg", "jpeg"} else "PNG"

    try:
        pil_image = Image.open(io.BytesIO(data))
    except UnidentifiedImageError:
        raise

    if image_format == "JPEG" and pil_image.mode not in {"RGB", "L"}:
        pil_image = pil_image.convert("RGB")

    buffer = io.BytesIO()
    save_kwargs = {"format": image_format}
    if image_format == "JPEG":
        save_kwargs.update({"quality": 90, "optimize": True})
    try:
        pil_image.save(buffer, **save_kwargs)
    except OSError as exc:
        logger.warning("Bild konnte nicht gespeichert werden (%s): %s", image_format, exc)
        return None

    payload = buffer.getvalue()
    file_path = directory / f"{stem}.{extension}"
    file_path.write_bytes(payload)

    b64_data = base64.b64encode(payload).decode("ascii")
    mime_type = "image/jpeg" if image_format == "JPEG" else "image/png"
    data_url = f"data:{mime_type};base64,{b64_data}"

    return ImageAssetPreparation(file_path=file_path, data_url=data_url, mime_type=mime_type)


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")
