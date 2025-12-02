"""Factory helpers to build LLM clients for the application."""
from __future__ import annotations

from typing import Optional

from .config import LlmConfig
from .llm_parser import OpenAiClient


def create_openai_client(llm_config: LlmConfig) -> Optional[OpenAiClient]:
    """Create an OpenAI client from the provided configuration.

    Raises:
        ValueError: If no API key is configured.
    """
    if not llm_config.api_key:
        raise ValueError("Kein OpenAI API Key konfiguriert")

    model_capabilities = {entry.id.lower(): entry.supports_sampling for entry in (llm_config.models or [])}

    return OpenAiClient(
        api_key=llm_config.api_key,
        model=llm_config.model,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        base_url=llm_config.base_url,
        timeout=llm_config.timeout,
        model_capabilities=model_capabilities,
    )
