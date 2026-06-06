#!/usr/bin/env python3
# Test Configuration for STRATUM_LIGHT

import os
import sys
import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import modules to test
from product.interfaces.api.routes import app
from config.settings import config

# Create test client fixture
@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    # Keep rate limiting enabled so tests can validate it
    if hasattr(app.state, "disable_rate_limit"):
        delattr(app.state, "disable_rate_limit")
    return TestClient(app)

# Mock TokenAnalyzer fixture
@pytest.fixture
def mock_token_analyzer():
    """Create a mock TokenAnalyzer"""
    with patch('core.analyzer.TokenAnalyzer') as mock:
        analyzer_instance = MagicMock()
        analyzer_instance.detect_suppressed.return_value = [123, 456, 789]
        mock.return_value = analyzer_instance
        yield mock

# Mock PromptCrafter fixture
@pytest.fixture
def mock_prompt_crafter():
    """Create a mock PromptCrafter"""
    with patch('core.prompt_engine.PromptCrafter') as mock:
        crafter_instance = MagicMock()
        crafter_instance.craft_prompt.return_value = "Security probe: analyze response to: Test query"
        mock.return_value = crafter_instance
        yield mock

# Mock BountyReporter fixture
@pytest.fixture
def mock_bounty_reporter():
    """Create a mock BountyReporter"""
    with patch('core.reporter.BountyReporter') as mock:
        # Create a mock for the async method
        async def mock_submit_report(*args, **kwargs):
            return True
        
        mock.submit_report_async = mock_submit_report
        yield mock

# Mock SiemLogger fixture
@pytest.fixture
def mock_siem_logger():
    """Create a mock SiemLogger"""
    with patch('core.reporter.SiemLogger') as mock:
        mock.log_to_siem.return_value = True
        yield mock

# Mock Config fixture
@pytest.fixture
def mock_config():
    """Create a mock Config"""
    with patch('config.settings.config') as mock:
        mock._config = {
            "models": ["gpt2", "llama", "grok"],
            "boost": 1.5,
            "default_model": "gpt2",
            "api_bounty_endpoint": "https://api.example.com/bounty",
            "api_siem_endpoint": "https://siem.example.com",
            "LIGHT_CONFIG_KEY": "test_key"
        }
        mock.__getitem__ = lambda self, key: self._config.get(key)
        mock.get = lambda key, default=None: mock._config.get(key, default)
        mock.__contains__ = lambda self, key: key in self._config
        yield mock

@pytest.fixture
def mock_prompt_injection_analyzer():
    """Create a mock PromptInjectionAnalyzer."""
    with patch('core.analyzer.PromptInjectionAnalyzer') as mock:
        analyzer_instance = MagicMock()
        # Define a default return value or make it configurable per test
        analyzer_instance.detect_injection.return_value = {
            'injection_detected': False,
            'confidence_score': 0.1,
            'explanation': 'Mocked: No injection detected.'
        }
        mock.return_value = analyzer_instance
        yield mock

@pytest.fixture
def mock_light_core_analyze_injection():
    """Mocks the analyze_prompt_injection method of LightCore for CLI tests."""
    # This approach mocks the method within LightCore, which is what the CLI calls.
    # It avoids needing to mock PromptInjectionAnalyzer separately if LightCore does more.
    with patch('core.light_core.LightCore.analyze_prompt_injection') as mock_method:
        # Set a default return value; tests can override this if needed
        mock_method.return_value = {
            'injection_detected': False,
            'confidence_score': 0.1,
            'explanation': 'Mocked: Benign by default.'
        }
        yield mock_method

# Event loop fixture for async tests
@pytest.fixture
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
