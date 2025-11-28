from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

PROMPT_DUMP_DIR = Path("data/prompts")


def log_prompt_messages(name: str, messages: Iterable[Any]) -> None:
    """
    Persist the LLM request messages to a file under data/prompts.
    This is best-effort and should never raise.
    """
    try:
        PROMPT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name).strip("_") or "prompt"
        filename = f"{timestamp}-{safe_name}.json"
        path = PROMPT_DUMP_DIR / filename
        path.write_text(json.dumps(list(messages), ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Saved LLM prompt to %s", path)
    except Exception as exc:  # pragma: no cover - best effort
        logger.debug("Could not save LLM prompt dump: %s", exc)
