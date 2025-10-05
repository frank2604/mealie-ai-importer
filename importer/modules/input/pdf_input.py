"""Load recipe data from PDF files."""
from __future__ import annotations

import logging

from ..context import PipelineContext
from ...pdf_extractor import PdfExtractionError, extract_text_and_images

logger = logging.getLogger(__name__)


class PdfInputModule:
    """Read the recipe PDF and store raw text plus images in the context."""

    name = "Input"

    def __init__(self, allow_empty_text: bool = False) -> None:
        self._allow_empty_text = allow_empty_text

    def run(self, context: PipelineContext) -> None:
        pdf_path = context.source_pdf
        logger.info("Lese PDF: %s", pdf_path)
        try:
            extraction = extract_text_and_images(pdf_path)
        except PdfExtractionError as exc:
            raise RuntimeError(f"PDF konnte nicht gelesen werden: {exc}") from exc

        if not extraction.text.strip() and not self._allow_empty_text:
            raise RuntimeError(
                "PDF enthielt keinen Text. Für gescannte Dokumente ist ggf. eine OCR nötig."
            )

        context.extraction = extraction
        logger.debug(
            "PDF eingelesen: %s Seiten, %s Zeichen Text, %s Bilder",
            extraction.page_count,
            len(extraction.text),
            len(extraction.images),
        )

