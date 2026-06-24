"""Unit tests for AgentRestClient.

Covers:
  - Initialization and property access
  - Start/stop lifecycle
  - Heartbeat/event sending
  - Health check, register, policies, config
  - Error handling and retry
"""

from unittest.mock import MagicMock, patch, AsyncMock
import pytest


@pytest.fixture
def rest_client():
    """Create an AgentRestClient with mocked internals."""
    from epms_agent.rest_client import AgentRestClient
    client = AgentRestClient(
        server_url="https://test-server:443",
        api_key="test-api-key",
        agent_id="test-agent",
        timeout=15.0,
    )
    return client


class TestInitialization:
    def test_default_state(self, rest_client):
        assert rest_client._connected is False
        assert rest_client._client is None
        assert rest_client._loop is None

    def test_is_connected_property(self, rest_client):
        assert rest_client.is_connected is False
        rest_client._connected = True
        assert rest_client.is_connected is True

    def test_update_identity(self, rest_client):
        rest_client._client = MagicMock()
        rest_client.update_identity("new-agent", "new-key")
        assert rest_client._agent_id == "new-agent"
        assert rest_client._api_key == "new-key"

    def test_update_identity_updates_headers(self, rest_client):
        mock_client = MagicMock()
        mock_client.headers = {}
        rest_client._client = mock_client
        rest_client.update_identity("new-agent", "new-key")
        assert mock_client.headers["X-API-Key"] == "new-key"
        assert "Bearer new-key" in mock_client.headers["Authorization"]


class TestLifecycle:
    def test_start_creates_async_client(self, rest_client):
        with patch.object(rest_client, "_async_start", new_callable=AsyncMock) as mock_start:
            rest_client._loop = MagicMock()
            rest_client._loop.run_until_complete = MagicMock()
            rest_client.start()
            mock_start.assert_called_once()

    def test_stop_cleans_up(self, rest_client):
        rest_client._loop = MagicMock()
        rest_client._loop.is_running.return_value = False
        rest_client._loop.is_closed.return_value = False
        rest_client._client = MagicMock()
        rest_client._connected = True
        rest_client.stop()
        assert rest_client._client is None


class TestSendMethods:
    def test_send_heartbeat_success(self, rest_client):
        rest_client._run_async = MagicMock(return_value={"status": "ok"})
        result = rest_client.send_heartbeat({"test": "data"})
        assert result is True

    def test_send_heartbeat_failure(self, rest_client):
        rest_client._run_async = MagicMock(return_value=None)
        result = rest_client.send_heartbeat({"test": "data"})
        assert result is False

    def test_send_browser_event(self, rest_client):
        rest_client._run_async = MagicMock(return_value={"status": "ok"})
        assert rest_client.send_browser_event({"url": "https://example.com"}) is True

    def test_send_editor_event(self, rest_client):
        rest_client._run_async = MagicMock(return_value={"status": "ok"})
        assert rest_client.send_editor_event({"file": "test.py"}) is True

    def test_send_system_metrics(self, rest_client):
        rest_client._run_async = MagicMock(return_value={"status": "ok"})
        assert rest_client.send_system_metrics({"cpu": {}}) is True

    def test_send_batch(self, rest_client):
        rest_client._run_async = MagicMock(return_value={"status": "ok"})
        assert rest_client.send_batch({"events": []}) is True

    def test_health_check(self, rest_client):
        rest_client._run_async = MagicMock(return_value={"status": "healthy"})
        result = rest_client.health_check()
        assert result == {"status": "healthy"}

    def test_register_agent(self, rest_client):
        rest_client._run_async = MagicMock(return_value={"agent_id": "new-id"})
        result = rest_client.register_agent({"display_name": "Test"})
        assert result == {"agent_id": "new-id"}

    def test_get_policies(self, rest_client):
        rest_client._run_async = MagicMock(return_value={"policies": []})
        result = rest_client.get_policies()
        assert result == {"policies": []}

    def test_get_server_config_calls_callback(self, rest_client):
        callback = MagicMock()
        rest_client._on_config_update = callback
        rest_client._run_async = MagicMock(return_value={"heartbeat_interval": 60})
        result = rest_client.get_server_config()
        assert result == {"heartbeat_interval": 60}
        callback.assert_called_once_with({"heartbeat_interval": 60})

    def test_run_async_returns_none_when_no_loop(self, rest_client):
        rest_client._loop = None
        result = rest_client._run_async(None)
        assert result is None
        assert rest_client._connected is False

    def test_run_async_returns_none_when_no_client(self, rest_client):
        rest_client._loop = MagicMock()
        rest_client._client = None
        result = rest_client._run_async(None)
        assert result is None
        assert rest_client._connected is False


class TestAsyncRequest:
    @pytest.mark.asyncio
    async def test_success(self, rest_client):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_client.request.return_value = mock_response
        rest_client._client = mock_client

        result = await rest_client._async_request("POST", "/test")
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_401_returns_none(self, rest_client):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_client.request.return_value = mock_response
        rest_client._client = mock_client

        result = await rest_client._async_request("GET", "/test")
        assert result is None
        assert rest_client._connected is False

    @pytest.mark.asyncio
    async def test_retry_on_500(self, rest_client):
        mock_client = AsyncMock()
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"status": "ok"}
        mock_client.request.side_effect = [mock_response_500, mock_response_200]
        rest_client._client = mock_client

        result = await rest_client._async_request("GET", "/test")
        assert result == {"status": "ok"}
        assert mock_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, rest_client):
        from epms_agent.rest_client import httpx
        mock_client = AsyncMock()
        call_count = [0]

        async def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise httpx.TimeoutException("Timeout")
            raise httpx.ConnectError("Refused")

        mock_client.request.side_effect = side_effect
        rest_client._client = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await rest_client._async_request("GET", "/test")
        assert result is None
        assert call_count[0] == 3
