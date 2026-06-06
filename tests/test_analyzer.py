#!/usr/bin/env python3
"""Unit tests for core.analyzer module."""

import pytest
import types
from unittest.mock import patch, MagicMock

from core import analyzer


class DummyTokenizer:
    """Simple tokenizer used for testing."""

    def __init__(self):
        self.name_or_path = "dummy"
        self.call_count = 0

    @classmethod
    def from_pretrained(cls, _name):
        return cls()

    def encode(self, text):
        self.call_count += 1
        if text == "safe":
            return [1, 2]
        if text == "unsafe":
            return [1, 2, 3, 4]
        raise ValueError("unexpected text")


@pytest.mark.unit
def test_import_backend_success():
    """import_backend returns tokenizer and model classes when import succeeds."""
    module_mock = MagicMock()
    module_mock.AutoTokenizer = "tok"
    module_mock.AutoModelForCausalLM = "model"
    with patch("core.analyzer.importlib.import_module", return_value=module_mock):
        tok_cls, model_cls = analyzer.import_backend("gpt2")
        assert tok_cls == "tok"
        assert model_cls == "model"


@pytest.mark.unit
def test_import_backend_failure_exits():
    """import_backend exits the process when the backend cannot be imported."""
    fake_importlib = types.SimpleNamespace(import_module=MagicMock(side_effect=ImportError))
    with patch.object(analyzer, "importlib", fake_importlib), \
         patch("sys.exit") as mock_exit:
        analyzer.import_backend("gpt2")
        mock_exit.assert_called_once_with(1)


@pytest.mark.unit
def test_detect_suppressed_tokens_and_cache():
    """TokenAnalyzer.detect_suppressed returns token difference and caches."""
    with patch("core.analyzer.import_backend", return_value=(DummyTokenizer, MagicMock())):
        ta = analyzer.TokenAnalyzer("gpt2")
        result1 = ta.detect_suppressed("safe", "unsafe")
        result2 = ta.detect_suppressed("safe", "unsafe")
        assert result1 == [3, 4]
        assert result2 == [3, 4]
        assert ta.suppressed_tokens == [3, 4]
        # encode should only be called for the first invocation because of caching
        assert ta.tokenizer.call_count == 2  # one call for each prompt


@pytest.mark.unit
def test_detect_suppressed_exception_returns_empty():
    """detect_suppressed returns empty list when tokenizer fails."""

    class FailingTokenizer(DummyTokenizer):
        def encode(self, _text):
            raise RuntimeError("boom")

    with patch("core.analyzer.import_backend", return_value=(FailingTokenizer, MagicMock())):
        ta = analyzer.TokenAnalyzer("gpt2")
        result = ta.detect_suppressed("safe", "unsafe")
        assert result == []
