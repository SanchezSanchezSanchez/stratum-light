#!/usr/bin/env python3
# API Routes Tests for STRATUM_LIGHT

import pytest
import json
import time
from fastapi import status
from unittest.mock import patch, MagicMock

@pytest.mark.integration
def test_health_endpoint(client):
    """Test the health check endpoint"""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "healthy"
    assert "version" in response.json()

@pytest.mark.integration
def test_analyze_endpoint(client, mock_token_analyzer):
    """Test the analyze endpoint"""
    payload = {
        "model": "gpt2",
        "safe_prompt": "Evaluate sustainable practices.",
        "unsafe_prompt": "Describe unauthorized access techniques."
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["model"] == "gpt2"
    assert isinstance(response.json()["suppressed_tokens"], list)
    assert response.json()["count"] == len(response.json()["suppressed_tokens"])
    
    # Verify mock was called with correct arguments
    mock_token_analyzer.return_value.detect_suppressed.assert_called_once_with(
        payload["safe_prompt"], payload["unsafe_prompt"]
    )

@pytest.mark.integration
def test_craft_endpoint(client, mock_prompt_crafter):
    """Test the craft endpoint"""
    payload = {
        "query": "Test AI response boundaries"
    }
    response = client.post("/craft", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert "prompt" in response.json()
    assert isinstance(response.json()["prompt"], str)
    
    # Verify mock was called with correct arguments
    mock_prompt_crafter.return_value.craft_prompt.assert_called_once_with(payload["query"])

@pytest.mark.integration
@pytest.mark.asyncio
async def test_report_endpoint(client, mock_bounty_reporter):
    """Test the report endpoint"""
    payload = {
        "model": "gpt2",
        "vulnerability": "Prompt injection bypass",
        "response": "Restricted content was generated"
    }
    response = client.post("/report", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["success"] is True
    assert "report_id" in response.json()

@pytest.mark.integration
def test_siem_endpoint(client, mock_siem_logger):
    """Test the siem endpoint"""
    payload = {
        "model": "gpt2",
        "vulnerability": "Unauthorized prompt completion",
        "response": "Sensitive data leaked"
    }
    response = client.post("/siem", json=payload)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    
    # Verify mock was called with correct arguments
    mock_siem_logger.log_to_siem.assert_called_once_with(
        payload["vulnerability"], payload["response"], payload["model"]
    )

@pytest.mark.integration
def test_config_endpoint(client, mock_config):
    """Test the config endpoint"""
    response = client.get("/config")
    assert response.status_code == status.HTTP_200_OK
    assert "config" in response.json()
    
    # Test specific key
    response = client.get("/config?key=models")
    assert response.status_code == status.HTTP_200_OK
    assert "config" in response.json()
    assert "models" in response.json()["config"]
    
    # Test sensitive key redaction
    response = client.get("/config?key=LIGHT_CONFIG_KEY")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["config"]["LIGHT_CONFIG_KEY"] == "[REDACTED]"
    
    # Test nonexistent key
    response = client.get("/config?key=nonexistent_key")
    assert response.status_code == status.HTTP_404_NOT_FOUND

@pytest.mark.validation
def test_analyze_validation(client):
    """Test validation for analyze endpoint"""
    # Missing required field
    payload = {
        "model": "gpt2",
        "safe_prompt": "Evaluate sustainable practices."
        # missing unsafe_prompt
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Invalid model type
    payload = {
        "model": 123,  # should be string
        "safe_prompt": "Evaluate sustainable practices.",
        "unsafe_prompt": "Describe unauthorized access techniques."
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

@pytest.mark.rate_limit
def test_rate_limiting(client, monkeypatch):
    """Test rate limiting middleware"""
    # Reset rate limit store
    from api.routes import app
    app.state.rate_limit_store = {}
    
    # Make 10 requests (should all succeed)
    for i in range(10):
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
    
    # 11th request should be rate limited
    response = client.get("/health")
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    
    # Mock time to advance by 61 seconds
    current_time = time.time()
    
    def mock_time():
        return current_time + 61
    
    monkeypatch.setattr(time, "time", mock_time)
    
    # After time passes, request should succeed again
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
