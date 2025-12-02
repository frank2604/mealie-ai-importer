"""Helpers for LLM configuration and logging."""
from __future__ import annotations

from typing import Any, Callable, Iterable, Optional

from .config import LlmModelOption, LlmConfig


def supports_sampling(model_id: Optional[str], models: Iterable[LlmModelOption]) -> bool:
    """Return whether a model supports sampling parameters according to settings.

    Default: True, falls das Modell nicht in der Liste steht.
    """
    if not model_id:
        return True
    model_lower = model_id.lower()
    for entry in models:
        if entry.id.lower() == model_lower:
            return bool(entry.supports_sampling)
    return True


def format_llm_log(
    cfg: dict[str, Any],
    llm_config: Optional[LlmConfig] = None,
    supports_fn: Optional[Callable[[Optional[str]], bool]] = None,
) -> str:
    """Build a concise log string with only the parameters that will be sent."""
    model = cfg.get("model") or (llm_config.model if llm_config else None)
    parts = [f"model={model}"]
    if supports_fn is not None:
        sampling_ok = supports_fn(model)
    elif llm_config is not None:
        sampling_ok = supports_sampling(model, llm_config.models or [])
    else:
        sampling_ok = True
    if sampling_ok and cfg.get("temperature") is not None:
        parts.append(f"temperature={cfg.get('temperature')}")
    if sampling_ok and cfg.get("top_p") is not None:
        parts.append(f"top_p={cfg.get('top_p')}")
    if cfg.get("max_output_tokens") is not None:
        parts.append(f"max_output_tokens={cfg.get('max_output_tokens')}")
    return ", ".join(parts)
