"""LLM-assisted cropping for recipe images."""
from __future__ import annotations

import base64
import io
import json
import logging
import time
from typing import Optional

from PIL import Image

from .config import LlmConfig
from .llm_parser import LlmParsingError, OpenAiClient, _parse_json_response  # reuse util
from .prompt_store import resolve_prompt, resolve_llm_config
from .prompt_logging import log_prompt_messages

logger = logging.getLogger(__name__)


def crop_image_with_llm(
    image_bytes: bytes,
    *,
    llm_config: LlmConfig,
    title: str,
    locale: str = "de",
) -> Optional[bytes]:
    """Use an OpenAI vision model to crop *image_bytes* to the plated dish."""

    model = llm_config.vision_model or llm_config.model
    if not model or not llm_config.api_key:
        return None

    b64_image = base64.b64encode(image_bytes).decode("ascii")

    prompt_cfg = resolve_prompt("imageCrop", locale, replacements={"title": title})
    llm_cfg = resolve_llm_config("imageCrop")
    logger.info(
        "LLM config (imageCrop): model=%s, temperature=%s, top_p=%s, max_output_tokens=%s",
        llm_cfg.get("model"),
        llm_cfg.get("temperature"),
        llm_cfg.get("top_p"),
        llm_cfg.get("max_output_tokens"),
    )
    system_prompt = prompt_cfg.get("system") or "Du bist ein präziser Assistent für Bildausschnitte."
    user_parts = [
        part.strip()
        for part in (prompt_cfg.get("user1", ""), prompt_cfg.get("user2", ""))
        if part and part.strip()
    ]
    user_text = "\n\n".join(user_parts) if user_parts else title

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_image}",
                    },
                },
            ],
        },
    ]

    log_prompt_messages("imageCrop", messages)

    client = OpenAiClient(
        api_key=llm_config.api_key,
        model=llm_cfg.get("model") or model,
        base_url=llm_config.base_url,
        timeout=llm_config.timeout,
    )

    # run_json erwartet system/user als Strings; wir geben die Messages als JSON-String weiter
    response_obj = None
    attempts = 3
    for attempt in range(1, attempts + 1):
        try:
            response_obj = client.run_json(system_prompt, json.dumps(messages), llm_config=llm_cfg)
            break
        except Exception as exc:  # pragma: no cover - defensive
            err_text = str(exc).lower()
            if "429" in err_text and attempt < attempts:
                wait = min(2 * attempt, 5)
                logger.info("Vision-Anfrage Rate-Limit (429) – Retry %s/%s in %ss", attempt, attempts, wait)
                time.sleep(wait)
                continue
            logger.warning("Vision-Anfrage fehlgeschlagen: %s", exc)
            return None

    if response_obj is None:
        logger.warning("Vision-Anfrage fehlgeschlagen: Keine Antwort nach Retries")
        return None

    result = response_obj if isinstance(response_obj, dict) else _parse_json_response(json.dumps(response_obj))

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
