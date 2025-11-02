"""Load recipe data from PDF files."""
from __future__ import annotations

import logging

from ..context import PipelineContext
from ...pdf_extractor import PdfExtractionError, extract_text_and_images

logger = logging.getLogger("PDF Input")


class PdfInputModule:
    """Read the recipe PDF and store raw text plus images in the context."""

    name = "Input"

    def __init__(self, allow_empty_text: bool = False) -> None:
        self._allow_empty_text = allow_empty_text

    def run(self, context: PipelineContext) -> None:
        pdf_path = context.source_pdf
        logger.info("Reading the recipe PDF from %s", pdf_path)
        try:
            extraction = extract_text_and_images(pdf_path)
        except PdfExtractionError as exc:
            raise RuntimeError(f"The PDF could not be read: {exc}") from exc

        if not extraction.text.strip() and not self._allow_empty_text:
            raise RuntimeError(
                "The PDF did not contain any text. Please enable OCR for scanned documents."
            )

        context.extraction = extraction
        logger.debug(
            "Finished reading the PDF: %s pages, %s text characters, %s images",
            extraction.page_count,
            len(extraction.text),
            len(extraction.images),
        )
