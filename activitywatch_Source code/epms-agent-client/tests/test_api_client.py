"""Unit tests for EPMSApiClient REST-only integration.

Covers:
  - Initialization and property access
  - REST client lifecycle (connect_rest / disconnect_rest)
  - send_heartbeat with REST path and offline buffering
  - health_check, register_agent
  - send_browser_event, send_editor_event, send_system_metrics
  - send_batch, get_policies, get_server_config
"""

from unittest.mock import MagicMock, patch, call, ANY
from typing import Dict, Any

import pytest


# ═══════════════════════════════════════════════════════════
# Initialization & Properties
# ═══════════════════════════════════════════════════════════

class TestInitialization:
    def test_default_state(self, api_client):
        assert api_client._connected is False
        assert api_client._agent_id is None
        assert api_client._server_info is None
        assert api_client._policies is None
        assert api_client._rest_client is None
        assert api_client._event_buffer is None
        assert api_client._last_connect_attempt == 0

    def test_api_key_property(self, api_client, agent_config):
        assert api_client.api_key == agent_config.server.api_key

    def test_base_url_property(self, api_client, agent_config):
        assert api_client.base_url == agent_config.server_url

    def test_is_connected_property(self, api_client):
        assert api_client.is_connected is False
        api_client._connected = True
        assert api_client.is_connected is True

    def test_agent_id_property(self, api_client):
        assert api_client.agent_id is None
        api_client._agent_id = "agent-123"
        assert api_client.agent_id == "agent-123"


# ═══════════════════════════════════════════════════════════
# REST Client Lifecycle
# ═══════════════════════════════════════════════════════════

class TestRestConnection:
    def test_connect_creates_rest_client(self, api_client, mock_rest_client_cls):
        mock_cls, mock_instance = mock_rest_client_cls

        api_client.connect_rest()

        mock_cls.assert_called_once_with(
            server_url=api_client.config.server_url,
            api_key="test-api-key",
            agent_id="",
            timeout=15.0,
            on_config_update=api_client._on_config_update,
            on_policy_push=api_client._on_policy_push,
            on_disconnected=api_client._on_disconnected,
        )
        mock_instance.start.assert_called_once()
        assert api_client._rest_client is mock_instance

    def test_connect_stops_existing(self, api_client, mock_rest_client_cls):
        _, mock_instance1 = mock_rest_client_cls
        api_client._rest_client = mock_instance1

        with patch("epms_agent.api_client.AgentRestClient") as mock_cls2:
            instance2 = MagicMock()
            mock_cls2.return_value = instance2
            api_client.connect_rest()
            mock_instance1.stop.assert_called_once()
            mock_cls2.assert_called_once()
            instance2.start.assert_called_once()
            assert api_client._rest_client is instance2

    def test_disconnect_stops_and_clears(self, api_client, mock_rest_client_cls):
        _, mock_instance = mock_rest_client_cls
        api_client._rest_client = mock_instance

        api_client.disconnect_rest()

        mock_instance.stop.assert_called_once()
        assert api_client._rest_client is None

    def test_disconnect_when_no_client(self, api_client):
        api_client._rest_client = None
        api_client.disconnect_rest()

    def test_on_disconnected_sets_false(self, api_client):
        api_client._connected = True
        api_client._on_disconnected()
        assert api_client._connected is False


# ═══════════════════════════════════════════════════════════
# send_heartbeat
# ═══════════════════════════════════════════════════════════

class TestSendHeartbeat:
    def test_sends_via_rest(self, api_client, mock_rest_client_cls, mock_heartbeat):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.send_heartbeat.return_value = True
        api_client._rest_client = rest_instance

        result = api_client.send_heartbeat()

        assert result is True
        rest_instance.send_heartbeat.assert_called_once_with(mock_heartbeat)

    def test_sends_browser_activity(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.send_heartbeat.return_value = True
        api_client._rest_client = rest_instance

        browser_data = {"browser_name": "Chrome", "url": "https://example.com"}
        mock_data = {
            "timestamp": "2024-01-01T00:00:00",
            "active_window": {"title": "Chrome", "process": "chrome.exe"},
            "browser_activity": browser_data,
            "editor_activity": None,
            "afk_seconds": 0.0,
            "is_afk": False,
            "system": {},
        }
        with patch("epms_agent.api_client.get_heartbeat_data", return_value=mock_data):
            result = api_client.send_heartbeat()

        assert result is True
        rest_instance.send_browser_event.assert_called_once_with(browser_data)
        rest_instance.send_editor_event.assert_not_called()

    def test_sends_editor_activity(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.send_heartbeat.return_value = True
        api_client._rest_client = rest_instance

        editor_data = {"editor_name": "VS Code", "file": "test.py"}
        mock_data = {
            "timestamp": "2024-01-01T00:00:00",
            "active_window": {"title": "test.py - VS Code", "process": "Code.exe"},
            "browser_activity": None,
            "editor_activity": editor_data,
            "afk_seconds": 0.0,
            "is_afk": False,
            "system": {},
        }
        with patch("epms_agent.api_client.get_heartbeat_data", return_value=mock_data):
            result = api_client.send_heartbeat()

        assert result is True
        rest_instance.send_editor_event.assert_called_once_with(editor_data)
        rest_instance.send_browser_event.assert_not_called()

    def test_skips_none_activities(self, api_client, mock_rest_client_cls, mock_heartbeat):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.send_heartbeat.return_value = True
        api_client._rest_client = rest_instance

        api_client.send_heartbeat()

        rest_instance.send_browser_event.assert_not_called()
        rest_instance.send_editor_event.assert_not_called()

    def test_buffers_when_offline(self, buffer_client, mock_heartbeat):
        client = buffer_client
        client._rest_client = None
        assert client._event_buffer is not None
        assert client._event_buffer.count_pending() == 0

        result = client.send_heartbeat()

        assert result is True
        assert client._event_buffer.count_pending() == 1

    def test_buffers_activities(self, buffer_client):
        client = buffer_client
        browser_data = {"browser_name": "Chrome"}
        editor_data = {"editor_name": "VS Code"}
        mock_data = {
            "timestamp": "2024-01-01T00:00:00",
            "active_window": {"title": "test.py", "process": "Code.exe"},
            "browser_activity": browser_data,
            "editor_activity": editor_data,
            "afk_seconds": 0.0,
            "is_afk": False,
            "system": {},
        }
        client._rest_client = None
        with patch("epms_agent.api_client.get_heartbeat_data", return_value=mock_data):
            result = client.send_heartbeat()
        assert result is True
        assert client._event_buffer.count_pending() == 3

    def test_returns_false_when_no_transport(self, api_client, mock_heartbeat):
        api_client._rest_client = None
        api_client._event_buffer = None
        result = api_client.send_heartbeat()
        assert result is False


# ═══════════════════════════════════════════════════════════
# send_browser_event / send_editor_event
# ═══════════════════════════════════════════════════════════

class TestSendBrowserEvent:
    def test_via_rest(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.send_browser_event.return_value = True
        api_client._rest_client = rest_instance
        data = {"url": "https://example.com"}

        result = api_client.send_browser_event(data)

        assert result is True
        rest_instance.send_browser_event.assert_called_once_with(data)

    def test_fails_when_disconnected(self, api_client):
        api_client._rest_client = None
        result = api_client.send_browser_event({"url": "x"})
        assert result is False


class TestSendEditorEvent:
    def test_via_rest(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.send_editor_event.return_value = True
        api_client._rest_client = rest_instance
        data = {"file": "test.py"}

        result = api_client.send_editor_event(data)

        assert result is True
        rest_instance.send_editor_event.assert_called_once_with(data)

    def test_fails_when_disconnected(self, api_client):
        api_client._rest_client = None
        result = api_client.send_editor_event({"file": "x"})
        assert result is False


# ═══════════════════════════════════════════════════════════
# send_system_metrics
# ═══════════════════════════════════════════════════════════

class TestSendSystemMetrics:
    def test_via_rest(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.send_system_metrics.return_value = True
        api_client._rest_client = rest_instance
        data = {"cpu": {"percent": 45.0}}

        result = api_client.send_system_metrics(data)

        assert result is True
        rest_instance.send_system_metrics.assert_called_once_with(data)

    def test_fails_when_disconnected(self, api_client):
        api_client._rest_client = None
        result = api_client.send_system_metrics({"cpu": {}})
        assert result is False


# ═══════════════════════════════════════════════════════════
# health_check & register_agent
# ═══════════════════════════════════════════════════════════

class TestHealthCheck:
    def test_200_returns_true(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.health_check.return_value = {"status": "healthy"}
        api_client._rest_client = rest_instance

        result = api_client.health_check()

        assert result is True
        assert api_client._connected is True
        assert api_client._server_info == {"status": "healthy"}

    def test_failure_returns_false(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.health_check.return_value = None
        api_client._rest_client = rest_instance

        result = api_client.health_check()

        assert result is False
        assert api_client._connected is False


class TestRegisterAgent:
    def test_success_updates_identity(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.register_agent.return_value = {
            "agent_id": "new-agent-456",
            "api_key": "new-api-key-789",
        }
        api_client._rest_client = rest_instance

        result = api_client.register_agent("My Machine")

        assert result is True
        assert api_client._agent_id == "new-agent-456"
        rest_instance.update_identity.assert_called_once_with(
            "new-agent-456", "new-api-key-789"
        )

    def test_accepts_id_key(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.register_agent.return_value = {"id": "alt-id-field"}
        api_client._rest_client = rest_instance

        result = api_client.register_agent()

        assert result is True
        assert api_client._agent_id == "alt-id-field"

    def test_same_agent_id_no_update(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.register_agent.return_value = {"agent_id": "existing-id"}
        api_client._rest_client = rest_instance
        api_client._agent_id = "existing-id"

        result = api_client.register_agent()

        assert result is True
        rest_instance.update_identity.assert_not_called()

    def test_failure_returns_false(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.register_agent.return_value = None
        api_client._rest_client = rest_instance

        result = api_client.register_agent("Test")

        assert result is False

    def test_payload_structure(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.register_agent.return_value = {"agent_id": "new-id"}
        api_client._rest_client = rest_instance

        with patch("epms_agent.api_client.EPMSApiClient._get_hostname",
                   return_value="test-pc"):
            api_client.register_agent("My PC")

        _, kwargs = rest_instance.register_agent.call_args
        payload = kwargs[0] if kwargs else rest_instance.register_agent.call_args[0][0]
        assert payload["display_name"] == "My PC"
        assert payload["hostname"] == "test-pc"
        assert payload["version"] == "1.0.0"
        assert payload["capabilities"]["browser_monitoring"] is True


# ═══════════════════════════════════════════════════════════
# send_batch, get_policies, get_server_config
# ═══════════════════════════════════════════════════════════

class TestSendBatch:
    def test_success(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.send_batch.return_value = True
        api_client._rest_client = rest_instance

        result = api_client.send_batch([{"type": "heartbeat"}])

        assert result is True

    def test_fails_when_disconnected(self, api_client):
        api_client._rest_client = None
        result = api_client.send_batch([{"type": "test"}])
        assert result is False


class TestGetPolicies:
    def test_success(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.get_policies.return_value = {"policy": "block_social"}
        api_client._rest_client = rest_instance

        result = api_client.get_policies()

        assert result == {"policy": "block_social"}

    def test_failure(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.get_policies.return_value = None
        api_client._rest_client = rest_instance

        result = api_client.get_policies()

        assert result is None

    def test_disconnected(self, api_client):
        api_client._rest_client = None
        result = api_client.get_policies()
        assert result is None


class TestGetServerConfig:
    def test_success(self, api_client, mock_rest_client_cls):
        _, rest_instance = mock_rest_client_cls
        rest_instance.is_connected = True
        rest_instance.get_server_config.return_value = {"heartbeat_interval": 60}
        api_client._rest_client = rest_instance

        result = api_client.get_server_config()

        assert result == {"heartbeat_interval": 60}

    def test_disconnected(self, api_client):
        api_client._rest_client = None
        result = api_client.get_server_config()
        assert result is None


# ═══════════════════════════════════════════════════════════
# Buffer replay
# ═══════════════════════════════════════════════════════════

class TestBufferReplay:
    def test_replay_buffer_sends_via_rest(self, buffer_client):
        client = buffer_client
        client._rest_client = MagicMock()
        client._rest_client.is_connected = True
        client._rest_client.send_heartbeat.return_value = True

        client._event_buffer.enqueue("heartbeat", {"test": 1})
        client._event_buffer.enqueue("heartbeat", {"test": 2})

        count = client.replay_buffer()

        assert count == 0
        assert client._rest_client.send_heartbeat.call_count == 2

    def test_replay_buffer_noop_when_disconnected(self, buffer_client):
        client = buffer_client
        client._rest_client = None

        client._event_buffer.enqueue("heartbeat", {"test": 1})
        count = client.replay_buffer()

        assert count == 0  # Buffer skipped (no REST client)
        assert client._event_buffer.count_pending() == 1  # Buffer not emptied
