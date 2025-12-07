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
    """Pick the most plausible recipe photo from embedded PDF images.

    Heuristik:
    - Bevorzugt frühere Seiten.
    - Bevorzugt Bilder, die nicht wie ein kompletter A4-Scan (sehr groß, ~1.4 Seitenverhältnis) wirken.
    - Größe zählt positiv, aber extrem große A4-Scans werden abgewertet.
    - Fällt auf die größte Datei zurück, falls keine Bewertung möglich.
    """

    images = list(images)
    if not images:
        return None

    def score(img: ExtractedImage) -> float:
        # Grundwerte
        area = (img.width or 0) * (img.height or 0)
        size_score = min(area / 100_000, 30)  # Wachstum abflachen

        # Seitenverhältnis-Check, um A4-Scans (≈1.41) abzuwerten
        if img.width and img.height and img.width > 0 and img.height > 0:
            ratio = max(img.width, img.height) / max(1, min(img.width, img.height))
        else:
            ratio = 1.0
        a4_penalty = abs(1.414 - ratio)  # je näher an A4, desto kleiner der Wert

        # Extrem große A4-ähnliche Bilder (oft reine Text-Seiten) stärker bestrafen
        huge_a4_penalty = 0.0
        if area > 4_000_000 and 1.2 <= ratio <= 1.6:
            huge_a4_penalty = 10.0

        # Frühe Seiten bevorzugen; fehlt page_number -> neutral
        page_bonus = 0.0
        if getattr(img, "page_number", None):
            # Seite 1: +6, Seite 2: +5, ...
            page_bonus = max(0.0, 7.0 - float(img.page_number))

        return size_score + page_bonus - (a4_penalty * 2.0) - huge_a4_penalty

    try:
        return max(images, key=score)
    except Exception:  # pragma: no cover - defensive fallback
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
