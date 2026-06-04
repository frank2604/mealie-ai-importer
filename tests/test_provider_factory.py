import pytest

from importer.config import LlmConfig, LlmModelOption
from importer.llm_factory import create_llm_client
from importer.llm_anthropic import AnthropicClient


def _cfg(provider, api_key="sk-x"):
    return LlmConfig(
        provider=provider,
        model="claude-haiku-4-5",
        temperature=None,
        max_tokens=None,
        api_key=api_key,
        models=[LlmModelOption("claude-haiku-4-5", True)],
    )


def test_anthropic_is_default():
    assert isinstance(create_llm_client(_cfg("")), AnthropicClient)
    assert isinstance(create_llm_client(_cfg("anthropic")), AnthropicClient)


def test_unknown_provider_raises():
    """OpenAI and other unknown providers are no longer supported."""
    with pytest.raises(ValueError, match="Unbekannter LLM-Provider"):
        create_llm_client(_cfg("openai"))


def test_missing_api_key_raises():
    with pytest.raises(ValueError):
        create_llm_client(_cfg("anthropic", api_key=None))
