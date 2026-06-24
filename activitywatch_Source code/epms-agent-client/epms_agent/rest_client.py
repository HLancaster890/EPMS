"""
REST API transport for EPMS Enterprise Server using httpx.

Replaces the legacy WebSocket client with async HTTP transport.
Heartbeats and events are sent via POST requests to the consolidated
EPMS server (port 8000). Supports connection pooling, timeouts,
and offline buffering via the event buffer callback.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, Callable

import httpx

logger = logging.getLogger(__name__)


class AgentRestClient:
    """Async REST client for EPMS server communication.

    Manages its own httpx.AsyncClient with connection pooling.
    Heartbeat/event methods are fire-and-forget from sync code
    via the internal event loop.
    """

    def __init__(
        self,
        server_url: str,
        api_key: str,
        agent_id: str = "",
        timeout: float = 15.0,
        on_config_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_policy_push: Optional[Callable[[List[Dict]], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None,
    ):
        self._server_url = server_url.rstrip("/")
        self._api_key = api_key
        self._agent_id = agent_id
        self._timeout = timeout
        self._on_config_update = on_config_update
        self._on_policy_push = on_policy_push
        self._on_disconnected = on_disconnected

        self._client: Optional[httpx.AsyncClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def start(self):
        """Start the async client in its own event loop thread."""
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._async_start())

    async def _async_start(self):
        """Initialize the httpx client."""
        self._client = httpx.AsyncClient(
            base_url=self._server_url,
            headers={
                "User-Agent": "EPMS-Agent-Client/1.0",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-API-Key": self._api_key,
                "Authorization": f"Bearer {self._api_key}",
            },
            timeout=httpx.Timeout(self._timeout),
            limits=httpx.Limits(max_keepalive_connections=4, max_connections=8),
        )
        self._connected = True
        logger.debug("REST client started")

    def stop(self):
        """Stop the async client."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._loop and not self._loop.is_closed():
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            self._loop.run_until_complete(self._async_stop())
            self._loop.close()
        self._client = None
        self._loop = None
        self._connected = False

    async def _async_stop(self):
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()

    def _run_async(self, coro):
        """Run an async coroutine from sync code."""
        if not self._loop or self._loop.is_closed():
            logger.warning("REST client loop not available")
            self._connected = False
            return None
        if not self._client:
            logger.warning("REST client not initialized")
            self._connected = False
            return None
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result(timeout=self._timeout + 5)
        except Exception as e:
            logger.debug(f"REST call failed: {e}")
            self._connected = False
            if self._on_disconnected:
                self._on_disconnected()
            return None

    def update_identity(self, agent_id: str, api_key: str):
        """Update agent identity after server registration."""
        self._agent_id = agent_id
        self._api_key = api_key
        if self._client:
            self._client.headers.update({
                "X-API-Key": api_key,
                "Authorization": f"Bearer {api_key}",
            })

    def health_check(self, timeout: float = 10.0) -> Optional[Dict]:
        """Check server health via GET /api/v1/health."""
        return self._run_async(self._async_request("GET", "/api/v1/health", timeout=timeout))

    def register_agent(self, payload: Dict) -> Optional[Dict]:
        """Register agent via POST /api/v1/agent/register."""
        return self._run_async(
            self._async_request("POST", "/api/v1/agent/register", json=payload)
        )

    def send_heartbeat(self, heartbeat_data: Dict) -> bool:
        """Send heartbeat via POST /api/v1/agent/heartbeat."""
        result = self._run_async(
            self._async_request("POST", "/api/v1/agent/heartbeat", json=heartbeat_data)
        )
        return result is not None

    def send_browser_event(self, browser_data: Dict) -> bool:
        """Send browser activity via POST /api/v1/agent/browser."""
        result = self._run_async(
            self._async_request("POST", "/api/v1/agent/browser", json=browser_data)
        )
        return result is not None

    def send_editor_event(self, editor_data: Dict) -> bool:
        """Send editor activity via POST /api/v1/agent/editor."""
        result = self._run_async(
            self._async_request("POST", "/api/v1/agent/editor", json=editor_data)
        )
        return result is not None

    def send_system_metrics(self, metrics_data: Dict) -> bool:
        """Send system metrics via POST /api/v1/agent/metrics."""
        result = self._run_async(
            self._async_request("POST", "/api/v1/agent/metrics", json=metrics_data)
        )
        return result is not None

    def send_batch(self, batch_data: Dict) -> bool:
        """Send batch events via POST /api/v1/agent/events/batch."""
        result = self._run_async(
            self._async_request("POST", "/api/v1/agent/events/batch", json=batch_data)
        )
        return result is not None

    def get_policies(self) -> Optional[Dict]:
        """Get policies via GET /api/v1/agent/policies."""
        return self._run_async(self._async_request("GET", "/api/v1/agent/policies"))

    def get_server_config(self) -> Optional[Dict]:
        """Get server config via GET /api/v1/agent/config."""
        result = self._run_async(self._async_request("GET", "/api/v1/agent/config"))
        if result:
            if self._on_config_update:
                self._on_config_update(result)
        return result

    async def _async_request(self, method: str, path: str, **kwargs) -> Optional[Dict]:
        """Make an async HTTP request with retry."""
        if not self._client:
            return None
        kwargs.setdefault("timeout", httpx.Timeout(self._timeout))
        if self._agent_id:
            headers = kwargs.pop("headers", {})
            headers["X-Agent-ID"] = self._agent_id
            kwargs["headers"] = headers

        for attempt in range(3):
            try:
                resp = await self._client.request(method, path, **kwargs)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code in (401, 403):
                    logger.warning(f"Auth error on {path}: {resp.status_code}")
                    self._connected = False
                    return None
                elif resp.status_code >= 500 and attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
                    continue
                else:
                    logger.debug(f"Unexpected status {resp.status_code} on {path}")
                    return None
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                if attempt < 2:
                    await asyncio.sleep(1.0 * (2 ** attempt))
                    continue
                logger.debug(f"Request failed for {path}: {e}")
                return None
        return None
