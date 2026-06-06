#!/usr/bin/env python3
"""Unit tests for the reporter module."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock, ANY, mock_open

from core.reporter import BountyReporter, SiemLogger


@pytest.mark.unit
def test_calculate_cvss_known_model():
    with patch("core.reporter.config", {"cvss_vector": "VECTOR"}):
        result = BountyReporter.calculate_cvss("gpt2")
    assert result == {"base_score": 9.0, "vector": "VECTOR"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_submit_report_async_success():
    endpoints = ["http://a", "http://b"]
    with patch("core.reporter.config", {"bounty_endpoints": endpoints, "cvss_vector": "V"}), \
         patch("core.reporter.aiohttp.ClientSession") as MockSession, \
         patch("os.getenv", return_value="TOKEN"):
        session = AsyncMock()
        MockSession.return_value.__aenter__.return_value = session
        cm = AsyncMock()
        cm.__aenter__.return_value = AsyncMock()
        session.post.return_value = cm

        await BountyReporter.submit_report_async("vuln", "resp", "gpt2")

        assert session.post.call_count == len(endpoints)
        session.post.assert_called_with(
            endpoints[-1], json=ANY, headers={"Authorization": "Bearer TOKEN"}
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_submit_report_async_failure_writes_file(tmp_path):
    endpoints = ["http://only"]
    file_mock = mock_open()
    with patch("core.reporter.config", {"bounty_endpoints": endpoints, "cvss_vector": "V"}), \
         patch("core.reporter.aiohttp.ClientSession") as MockSession, \
         patch("builtins.open", file_mock), \
         patch("os.getenv", return_value="TOKEN"):
        session = AsyncMock()
        MockSession.return_value.__aenter__.return_value = session
        session.post.side_effect = Exception("boom")
        await BountyReporter.submit_report_async("v", "r", "gpt2")
        file_mock.assert_called()  # report saved locally on failure


@pytest.mark.unit
def test_siem_logger_posts_event():
    with patch("core.reporter.config", {"siem_endpoint": "http://siem"}), \
         patch("core.reporter.requests.post") as mock_post:
        SiemLogger.log_to_siem("v", "r", "gpt2")
        mock_post.assert_called_once_with(
            "http://siem",
            json=ANY,
        )
