from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

PROMPT_DUMP_DIR = Path("data/prompts")


def log_prompt_messages(name: str, messages: Iterable[Any]) -> str:
    """
    Persist the LLM request messages to a file under data/prompts.
    This is best-effort and should never raise.

    Returns:
        The generated file stem (without suffix), so responses can be stored alongside.
    """
    try:
        PROMPT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name).strip("_") or "prompt"
        stem = f"{timestamp}-{safe_name}"
        path = PROMPT_DUMP_DIR / f"{stem}-request.json"
        path.write_text(json.dumps(list(messages), ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Saved LLM prompt to %s", path)
        return stem
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("Could not save LLM prompt dump: %s", exc)
        return ""


def log_prompt_response(name: str, response: Any, *, stem: str | None = None) -> None:
    """Persist the LLM response alongside the prompt, if possible."""
    try:
        PROMPT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
        if not stem:
            timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")[:-3]
            safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name).strip("_") or "prompt"
            stem = f"{timestamp}-{safe_name}"
        path = PROMPT_DUMP_DIR / f"{stem}-response.json"
        path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Saved LLM response to %s", path)
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("Could not save LLM response dump: %s", exc)
