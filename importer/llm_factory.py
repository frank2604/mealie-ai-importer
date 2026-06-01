"""Factory helpers to build LLM clients for the application."""
from __future__ import annotations

from typing import Any, Optional

from .config import LlmConfig
from .llm_parser import OpenAiClient
from .llm_anthropic import AnthropicClient


def _model_capabilities(llm_config: LlmConfig) -> dict:
    return {entry.id.lower(): entry.supports_sampling for entry in (llm_config.models or [])}


def create_llm_client(llm_config: LlmConfig) -> Any:
    """Create an LLM client based on the configured provider.

    Supported providers:
        - ``anthropic`` (default): Claude via the official SDK.
        - ``openai``: legacy OpenAI Chat Completions client (still functional).

    Raises:
        ValueError: If no API key is configured.
    """
    provider = (llm_config.provider or "anthropic").strip().lower()

    if not llm_config.api_key:
        raise ValueError(f"Kein API Key konfiguriert (provider={provider})")

    capabilities = _model_capabilities(llm_config)

    if provider == "openai":
        return OpenAiClient(
            api_key=llm_config.api_key,
            model=llm_config.model,
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            base_url=llm_config.base_url,
            timeout=llm_config.timeout,
            model_capabilities=capabilities,
        )

    # Default: Anthropic / Claude
    return AnthropicClient(
        api_key=llm_config.api_key,
        model=llm_config.model,
        temperature=llm_config.temperature,
        max_tokens=llm_config.max_tokens,
        base_url=llm_config.base_url,
        timeout=llm_config.timeout,
        model_capabilities=capabilities,
    )


def create_openai_client(llm_config: LlmConfig) -> Optional[Any]:
    """Backwards-compatible alias that now respects the configured provider."""
    return create_llm_client(llm_config)
