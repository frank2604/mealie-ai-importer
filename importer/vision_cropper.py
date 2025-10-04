"""LLM-assisted cropping for recipe images."""
from __future__ import annotations

import base64
import io
import json
import logging
from typing import Optional

import httpx
from PIL import Image

from .config import LlmConfig
from .llm_parser import LlmParsingError, _parse_json_response  # reuse util

logger = logging.getLogger(__name__)


_CROP_PROMPT = """
Finde ausschließlich die Bildregion, auf der das fertig angerichtete Gericht zu sehen ist. 
Es soll das komplette Gericht mit dem Gefäß (Teller, Schale, Schüssel, Glas, Becher etc.) zu sehen sein. 
Keine Cloe-Ups.
Ignoriere aber Textspalten, Seitenränder, Logos oder Dekoelemente. Gib ein JSON-Objekt mit dem 
Feld "crop" zurück. "crop" enthält relative Koordinaten innerhalb des Bildes (Werte von 0.0 bis 1.0):
{
  "crop": {
    "x": <linker Rand>,
    "y": <oberer Rand>,
    "width": <Breite>,
    "height": <Höhe>
  }
}
Falls kein sinnvolles Gericht zu erkennen ist, setze "crop" auf null.
""".strip()


def crop_image_with_llm(image_bytes: bytes, *, llm_config: LlmConfig, title: str) -> Optional[bytes]:
    """Use an OpenAI vision model to crop *image_bytes* to the plated dish."""

    model = llm_config.vision_model or llm_config.model
    if not model or not llm_config.api_key:
        return None

    b64_image = base64.b64encode(image_bytes).decode("ascii")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Du bist ein präziser Assistent für Bildausschnitte."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Rezept: {title}\n{_CROP_PROMPT}"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_image}",
                        },
                    },
                ],
            },
        ],
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {llm_config.api_key}",
        "Content-Type": "application/json",
    }

    endpoint = f"{llm_config.base_url.rstrip('/')}/chat/completions"

    try:
        response = httpx.post(endpoint, headers=headers, json=payload, timeout=llm_config.timeout)
    except httpx.HTTPError as exc:  # pragma: no cover - network issues
        logger.warning("Vision-Anfrage fehlgeschlagen: %s", exc)
        return None

    if response.status_code >= 400:
        logger.warning("Vision-Modell antwortete mit %s: %s", response.status_code, response.text[:200])
        return None

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("Vision-Antwort nicht lesbar: %s", exc)
        return None

    try:
        result = _parse_json_response(content)
    except LlmParsingError as exc:  # pragma: no cover - defensive
        logger.warning("Vision-Antwort kein JSON: %s", exc)
        return None

    crop = result.get("crop")
    if not crop:
        return None

    try:
        x = float(crop["x"])
        y = float(crop["y"])
        w = float(crop["width"])
        h = float(crop["height"])
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("Ungültige Crop-Koordinaten: %s", exc)
        return None

    if w <= 0 or h <= 0:
        return None

    try:
        image = Image.open(io.BytesIO(image_bytes))
    except Exception as exc:  # pragma: no cover - invalid image
        logger.warning("Pillow konnte Bild nicht öffnen: %s", exc)
        return None

    width, height = image.size
    left = max(0, min(width, round(x * width)))
    upper = max(0, min(height, round(y * height)))
    right = max(left + 1, min(width, round((x + w) * width)))
    lower = max(upper + 1, min(height, round((y + h) * height)))

    if right - left < width * 0.1 or lower - upper < height * 0.1:
        logger.warning("Berechneter Zuschnitt ist zu klein – verwende Originalbild")
        return None

    cropped = image.crop((left, upper, right, lower))
    buffer = io.BytesIO()
    cropped.save(buffer, format="PNG")
    return buffer.getvalue()
