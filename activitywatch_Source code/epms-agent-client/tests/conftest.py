"""Shared fixtures for EPMS Agent REST client tests."""

import json
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Optional

import pytest


class MockTimeoutException(Exception):
    pass


class MockConnectError(Exception):
    pass


@pytest.fixture
def agent_config():
    """Create a test AgentConfig for the API client."""
    from epms_agent.config import AgentConfig, ServerConfig, MonitoringConfig
    return AgentConfig(
        server=ServerConfig(
            host="test-server",
            port=443,
            use_ssl=True,
            api_key="test-api-key",
        ),
        monitoring=MonitoringConfig(
            enabled=True,
            heartbeat_interval_seconds=30,
            afk_timeout_minutes=5,
        ),
        display_name="Test Agent",
        agent_id="",
        auto_start=True,
    )


@pytest.fixture
def mock_rest_client_cls():
    """Patch AgentRestClient within the api_client module."""
    with patch("epms_agent.api_client.AgentRestClient") as mock_cls:
        instance = MagicMock()
        instance.is_connected = False
        mock_cls.return_value = instance
        yield mock_cls, instance


@pytest.fixture
def mock_rest_client():
    """Create a standalone mock AgentRestClient for direct tests."""
    with patch("epms_agent.rest_client.AgentRestClient", autospec=True) as mock_cls:
        instance = MagicMock()
        instance.is_connected = True
        mock_cls.return_value = instance
        yield instance


@pytest.fixture
def api_client(agent_config, mock_rest_client_cls):
    """Create an EPMSApiClient with all external deps mocked."""
    agent_config.buffer.enabled = False
    from epms_agent.api_client import EPMSApiClient
    return EPMSApiClient(agent_config)


@pytest.fixture
def buffer_client(agent_config, mock_rest_client_cls):
    """Create an EPMSApiClient with buffer enabled and a temp DB path."""
    import os
    import tempfile
    import shutil
    agent_config.buffer.enabled = True
    from epms_agent.api_client import EPMSApiClient
    client = EPMSApiClient(agent_config)
    if client._event_buffer:
        client._event_buffer.close()
    tmpdir = tempfile.mkdtemp()
    tmp_db = os.path.join(tmpdir, "test_events.db")
    from epms_agent.event_buffer import EventBuffer
    client._event_buffer = EventBuffer(tmp_db, max_events=100, max_age_days=7)
    yield client
    if client._event_buffer:
        client._event_buffer.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mock_heartbeat():
    """Patch get_heartbeat_data to return a known heartbeat dict."""
    data = {
        "timestamp": "2024-01-01T00:00:00",
        "active_window": {"title": "Visual Studio Code", "process": "Code.exe"},
        "browser_activity": None,
        "editor_activity": None,
        "afk_seconds": 0.0,
        "is_afk": False,
        "system": {"cpu": {"percent": 10.0}, "memory": {"percent": 50.0}},
    }
    with patch("epms_agent.api_client.get_heartbeat_data", return_value=data) as mock_fn:
        yield data
