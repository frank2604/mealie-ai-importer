"""Factory helpers to build LLM clients for the application."""
from __future__ import annotations

from typing import Any, Optional

from .config import LlmConfig
from .llm_anthropic import AnthropicClient


def _model_capabilities(llm_config: LlmConfig) -> dict:
    return {entry.id.lower(): entry.supports_sampling for entry in (llm_config.models or [])}


def create_llm_client(llm_config: LlmConfig) -> Any:
    """Create an LLM client based on the configured provider.

    Currently only the ``anthropic`` provider (Claude) is supported.
    The legacy ``openai`` provider has been removed — configure
    ``provider: anthropic`` in settings.yaml.

    Raises:
        ValueError: If no API key is configured or an unknown provider is given.
    """
    provider = (llm_config.provider or "anthropic").strip().lower()

    if not llm_config.api_key:
        raise ValueError(f"Kein API Key konfiguriert (provider={provider})")

    if provider not in ("anthropic", ""):
        raise ValueError(
            f"Unbekannter LLM-Provider '{provider}'. "
            "Nur 'anthropic' wird unterstützt. Bitte settings.yaml anpassen."
        )

    capabilities = _model_capabilities(llm_config)

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
    """Backwards-compatible alias — delegates to create_llm_client."""
    return create_llm_client(llm_config)
