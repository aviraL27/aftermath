import pytest
from aftermath.adapters.mock import MockAdapter
from aftermath.adapters.gemma import GemmaAdapter
from aftermath.adapters.mistral import MistralAdapter

def test_mock_adapter_step_sequence():
    adapter = MockAdapter(mode="buggy")
    a1 = adapter.step("test", [], [], ["config/app.json"])
    assert a1.tool_name == "read_file"

    history = [
        {"role": "assistant", "content": "read_file"},
        {"role": "system", "content": "read ok"}
    ]
    a2 = adapter.step("test", history, [], ["config/app.json"])
    assert a2.tool_name == "write_file"

def test_gemma_adapter_initialization():
    adapter = GemmaAdapter(primary_provider="google")
    assert adapter.name == "gemma4"
    assert adapter.primary_provider == "google"
    assert adapter.fallback_provider == "ollama"

def test_mistral_adapter_initialization():
    adapter = MistralAdapter()
    assert adapter.name == "mistral"
    assert adapter.model == "open-mistral-7b"

