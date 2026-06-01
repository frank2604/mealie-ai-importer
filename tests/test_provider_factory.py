import pytest

from importer.config import LlmConfig, LlmModelOption
from importer.llm_factory import create_llm_client
from importer.llm_anthropic import AnthropicClient
from importer.llm_parser import OpenAiClient


def _cfg(provider, api_key="sk-x"):
    return LlmConfig(
        provider=provider,
        model="claude-haiku-4-5" if provider != "openai" else "gpt-4.1-mini",
        temperature=None,
        max_tokens=None,
        api_key=api_key,
        models=[LlmModelOption("claude-haiku-4-5", True)],
    )


def test_anthropic_is_default():
    assert isinstance(create_llm_client(_cfg("")), AnthropicClient)
    assert isinstance(create_llm_client(_cfg("anthropic")), AnthropicClient)


def test_openai_still_supported():
    assert isinstance(create_llm_client(_cfg("openai")), OpenAiClient)


def test_missing_api_key_raises():
    with pytest.raises(ValueError):
        create_llm_client(_cfg("anthropic", api_key=None))
