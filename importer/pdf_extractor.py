"""Helpers for extracting raw text and images from PDF recipe files."""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PIL import Image, UnidentifiedImageError

from pypdf import PdfReader

logger = logging.getLogger(__name__)


@dataclass
class ExtractedImage:
    name: str
    data: bytes
    mime_type: str
    page_number: int
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class PdfExtractionResult:
    text: str
    images: List[ExtractedImage]
    page_count: int
    source_path: Path


class PdfExtractionError(Exception):
    """Raised when we cannot read a PDF file."""


def extract_text_and_images(pdf_path: Path) -> PdfExtractionResult:
    """Return the plain text and any embedded images for *pdf_path*.

    The function prefers embedded text. OCR is out of scope for the initial
    prototype but can be layered on top by checking for an empty text result.
    """

    if not pdf_path.exists():
        raise PdfExtractionError(f"PDF not found: {pdf_path}")

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:  # pragma: no cover - defensive, pypdf raises many types
        raise PdfExtractionError(f"Failed to open {pdf_path}: {exc}") from exc

    text_chunks: List[str] = []
    images: List[ExtractedImage] = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Text extraction failed on page %s: %s", page_number, exc)
            text = ""
        text_chunks.append(text.strip())

        try:
            page_images = list(getattr(page, "images", []))
        except ImportError as exc:
            logger.warning("Bildextraktion auf Seite %s übersprungen: %s", page_number, exc)
            page_images = []

        for index, image in enumerate(page_images, start=1):
            try:
                image_bytes = image.data  # type: ignore[attr-defined]
            except AttributeError:
                image_bytes = image.get_data()  # type: ignore[call-arg]

            width: Optional[int] = None
            height: Optional[int] = None
            try:
                with Image.open(io.BytesIO(image_bytes)) as pil_image:  # type: ignore[name-defined]
                    width, height = pil_image.size
            except (UnidentifiedImageError, Exception):  # pragma: no cover - best effort
                pass

            name = image.name or f"page{page_number}_image{index}"
            images.append(
                ExtractedImage(
                    name=name,
                    data=bytes(image_bytes),
                    mime_type=_guess_mime_type(image),
                    page_number=page_number,
                    width=width,
                    height=height,
                )
            )

    joined_text = "\n\n".join(chunk for chunk in text_chunks if chunk)
    logger.debug(
        "Extracted %s characters and %s images from %s",
        len(joined_text),
        len(images),
        pdf_path,
    )

    return PdfExtractionResult(
        text=joined_text,
        images=images,
        page_count=len(reader.pages),
        source_path=pdf_path,
    )


def _guess_mime_type(image_obj: object) -> str:
    """Best-effort MIME type detection for images produced by pypdf."""
    try:
        if hasattr(image_obj, "image_format") and image_obj.image_format:
            image_format = image_obj.image_format.lower()
        elif hasattr(image_obj, "name") and image_obj.name:
            image_format = Path(image_obj.name).suffix.lstrip(".").lower()
        else:
            image_format = "jpeg"
    except Exception:  # pragma: no cover - defensive
        image_format = "jpeg"

    mapping = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "tiff": "image/tiff",
        "bmp": "image/bmp",
    }

    return mapping.get(image_format, "image/jpeg")
