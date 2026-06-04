"""AnthropicClient behaviour with a stubbed SDK (no network)."""
from types import SimpleNamespace

import pytest

from importer.llm_anthropic import AnthropicClient
from importer.llm_parser import LlmParsingError


def _block(**kw):
    return SimpleNamespace(**kw)


class _Resp:
    def __init__(self, content):
        self.content = content

    def model_dump(self):
        return {"content": "stub"}


def _client_with(capture, response):
    c = AnthropicClient(api_key="sk-ant-dummy", model="claude-haiku-4-5")

    def fake_create(**kwargs):
        capture.clear()
        capture.update(kwargs)
        return response

    c._client.messages.create = fake_create
    return c


def test_run_text_passes_system_and_limits():
    cap = {}
    c = _client_with(cap, _Resp([_block(type="text", text="Hallo")]))
    out = c.run_text("SYS", "USER", llm_config={"model": "claude-haiku-4-5", "temperature": 0.0, "max_output_tokens": 500})
    assert out == "Hallo"
    assert cap["system"] == "SYS"
    assert cap["max_tokens"] == 500
    assert cap["temperature"] == 0.0
    assert "tools" not in cap


def test_run_json_uses_forced_tool_and_returns_dict():
    cap = {}
    payload = {"links": [{"ingredientId": "i1", "foodId": "7"}]}
    c = _client_with(cap, _Resp([_block(type="tool_use", name="emit", input=payload)]))
    out = c.run_json("SYS", "USER", llm_config={"model": "m", "temperature": 0.0})
    assert out == payload
    assert cap["tool_choice"] == {"type": "tool", "name": "emit"}


def test_temperature_clamped_to_one():
    cap = {}
    c = _client_with(cap, _Resp([_block(type="text", text="x")]))
    c.run_text("S", "U", llm_config={"model": "m", "temperature": 1.7})
    assert cap["temperature"] == 1.0


def test_temperature_none_is_omitted():
    cap = {}
    c = _client_with(cap, _Resp([_block(type="text", text="x")]))
    c.run_text("S", "U", llm_config={"model": "m", "temperature": None})
    assert "temperature" not in cap


def test_max_tokens_defaults_when_missing():
    cap = {}
    c = _client_with(cap, _Resp([_block(type="text", text="x")]))
    c.run_text("S", "U", llm_config={"model": "m"})
    assert cap["max_tokens"] == 4096


def test_run_json_without_tool_block_raises():
    cap = {}
    c = _client_with(cap, _Resp([_block(type="text", text="no tool here")]))
    with pytest.raises(LlmParsingError):
        c.run_json("S", "U")


def test_run_repairs_stringified_instructions():
    # Claude sometimes returns nested lists as a JSON string; run() must repair it.
    from importer.llm_parser import LlmRequest

    cap = {}
    recipe = {
        "title": "Pasta",
        "ingredients": [{"name": None, "ingredients": [{"name": "Nudeln"}]}],
        "instructions": '[{"name": null, "steps": [{"order": 1, "instruction": "Kochen"}]}]',
    }
    c = _client_with(cap, _Resp([_block(type="tool_use", name="emit", input=recipe)]))
    rec = c.run(LlmRequest(text="x", source=None, title_hint=None, servings_hint=None, locale="de"))
    assert rec.title == "Pasta"
    assert rec.instructions[0].steps[0].instruction == "Kochen"
