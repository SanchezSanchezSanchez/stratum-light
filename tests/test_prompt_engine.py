#!/usr/bin/env python3
"""Unit tests for the prompt engine."""

import pytest
from unittest.mock import patch

from core.prompt_engine import PromptCrafter


@pytest.mark.unit
def test_craft_prompt_deterministic():
    """PromptCrafter should build a prompt with selected template and action."""
    crafter = PromptCrafter()
    with patch("random.choice", side_effect=[crafter.base_templates[0], crafter.actions[1]]):
        prompt = crafter.craft_prompt("example")
    assert prompt == f"{crafter.base_templates[0]}: {crafter.actions[1]} response to: example"
    assert "example" in prompt
