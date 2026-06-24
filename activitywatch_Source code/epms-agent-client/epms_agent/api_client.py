"""
API client for communicating with the EPMS Enterprise Server.
Handles authentication via API key, registration, config management,
and REST-only transport using httpx.

All communication is via REST. No WebSocket dependency.
Offline resilience via SQLite event buffer.
"""

import logging
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from .config import AgentConfig, save_config
from .monitor import get_heartbeat_data
from .rest_client import AgentRestClient
from .event_buffer import EventBuffer

logger = logging.getLogger(__name__)

# REST API retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0
RETRY_BACKOFF_MAX = 10.0


class EPMSApiClient:
    """Client for EPMS Server REST API — no WebSocket dependency."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self._connected = False
        self._last_connect_attempt = 0
        self._server_info: Optional[Dict[str, Any]] = None
        self._agent_id: Optional[str] = None
        self._policies: Optional[Dict[str, Any]] = None
        self._rest_client: Optional[AgentRestClient] = None
        self._event_buffer: Optional[EventBuffer] = None
        if config.buffer.enabled:
            try:
                self._event_buffer = EventBuffer(
                    db_path=config.buffer.db_path,
                    max_events=config.buffer.max_events,
                    max_age_days=config.buffer.max_age_days,
                )
            except Exception as e:
                logger.warning(f"Failed to initialize event buffer: {e}")

    @property
    def api_key(self) -> str:
        return self.config.server.api_key

    @property
    def base_url(self) -> str:
        return self.config.server_url

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def agent_id(self) -> Optional[str]:
        return self._agent_id

    def connect_rest(self):
        """Initialize the async REST client."""
        if self._rest_client:
            self._rest_client.stop()

        agent_id = self._agent_id or self.config.agent_id or ""

        self._rest_client = AgentRestClient(
            server_url=self.config.server_url,
            api_key=self.config.server.api_key,
            agent_id=agent_id,
            timeout=15.0,
            on_config_update=self._on_config_update,
            on_policy_push=self._on_policy_push,
            on_disconnected=self._on_disconnected,
        )
        self._rest_client.start()
        logger.info(
            f"REST client initialized ({self.config.server.host}:{self.config.server.port})"
        )

    def disconnect_rest(self):
        """Stop the async REST client."""
        if self._rest_client:
            self._rest_client.stop()
            self._rest_client = None

    def _on_config_update(self, config: Dict[str, Any]):
        logger.info(f"Server config update received: {config}")
        self._policies = config

    def _on_policy_push(self, policies: list):
        logger.info(f"Received {len(policies)} policies from server")
        self._policies = {"policies": policies}

    def _on_disconnected(self):
        self._connected = False
        logger.warning("REST connection lost")

    def health_check(self) -> bool:
        """Check if the EPMS server is reachable and healthy."""
        if not self._rest_client:
            self.connect_rest()
        try:
            data = self._rest_client.health_check()
            if data:
                self._server_info = data
                self._connected = True
                logger.info(f"Server health check OK: {self.base_url}")
                return True
            else:
                logger.warning(f"Server health check failed")
                self._connected = False
                return False
        except Exception as e:
            logger.warning(f"Server health check failed: {e}")
            self._connected = False
            return False

    def register_agent(self, display_name: str = "") -> bool:
        """Register this agent with the EPMS server."""
        import platform
        if not self._rest_client:
            self.connect_rest()
        try:
            payload = {
                "display_name": display_name or "",
                "hostname": self._get_hostname(),
                "version": "1.0.0",
                "os": platform.system() or "unknown",
                "capabilities": {
                    "browser_monitoring": True,
                    "editor_monitoring": True,
                    "system_monitoring": True,
                    "window_monitoring": True,
                    "afk_detection": True,
                },
            }
            data = self._rest_client.register_agent(payload)
            if data:
                new_agent_id = data.get("agent_id") or data.get("id")
                new_api_key = data.get("api_key", self.config.server.api_key)
                if new_agent_id and new_agent_id != self._agent_id:
                    self._agent_id = new_agent_id
                    self._rest_client.update_identity(new_agent_id, new_api_key)
                # Persist the API key and agent_id to config for next startup
                if new_api_key and new_api_key != self.config.server.api_key:
                    self.config.server.api_key = new_api_key
                if new_agent_id:
                    self.config.agent_id = new_agent_id
                save_config(self.config)
                logger.info("Agent registered successfully")
                return True
            else:
                logger.warning("Agent registration failed")
                return False
        except Exception as e:
            logger.warning(f"Agent registration failed: {e}")
            return False

    def send_heartbeat(self, afk_timeout_minutes: int = 5) -> bool:
        """Send a heartbeat with monitoring data via REST.

        Falls back to SQLite buffer when server is unreachable.
        """
        heartbeat = get_heartbeat_data(afk_timeout_minutes)

        if self._rest_client and self._rest_client.is_connected:
            try:
                ok = self._rest_client.send_heartbeat(heartbeat)
                if ok:
                    if heartbeat.get("browser_activity"):
                        self._rest_client.send_browser_event(heartbeat["browser_activity"])
                    if heartbeat.get("editor_activity"):
                        self._rest_client.send_editor_event(heartbeat["editor_activity"])
                    return True
            except Exception as e:
                logger.debug(f"REST heartbeat failed, buffering: {e}")

        if self._event_buffer:
            self._event_buffer.enqueue("heartbeat", heartbeat)
            if heartbeat.get("browser_activity"):
                self._event_buffer.enqueue("browser_activity", heartbeat["browser_activity"])
            if heartbeat.get("editor_activity"):
                self._event_buffer.enqueue("editor_activity", heartbeat["editor_activity"])
            return True

        return False

    def send_browser_event(self, browser_data: Dict[str, Any]) -> bool:
        """Send a browser activity event via REST."""
        if not self._rest_client or not self._rest_client.is_connected:
            return False
        try:
            return self._rest_client.send_browser_event(browser_data)
        except Exception:
            return False

    def send_editor_event(self, editor_data: Dict[str, Any]) -> bool:
        """Send an editor activity event via REST."""
        if not self._rest_client or not self._rest_client.is_connected:
            return False
        try:
            return self._rest_client.send_editor_event(editor_data)
        except Exception:
            return False

    def send_batch(self, events: List[Dict[str, Any]]) -> bool:
        """Send a batch of monitoring events to the server via REST."""
        if not self._rest_client or not self._rest_client.is_connected:
            return False
        try:
            return self._rest_client.send_batch({
                "events": events,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "agent_id": self._agent_id,
            })
        except Exception:
            return False

    def get_policies(self) -> Optional[Dict[str, Any]]:
        """Get agent configuration policies from the server."""
        if not self._rest_client or not self._rest_client.is_connected:
            return None
        try:
            return self._rest_client.get_policies()
        except Exception:
            return None

    def get_server_config(self) -> Optional[Dict[str, Any]]:
        """Get agent configuration from the server."""
        if not self._rest_client or not self._rest_client.is_connected:
            return None
        try:
            return self._rest_client.get_server_config()
        except Exception:
            return None

    def send_system_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Send system metrics via REST."""
        if not self._rest_client or not self._rest_client.is_connected:
            return False
        try:
            return self._rest_client.send_system_metrics(metrics)
        except Exception:
            return False

    def replay_buffer(self) -> int:
        """Replay buffered events via REST."""
        if not self._event_buffer or not self._rest_client or not self._rest_client.is_connected:
            return 0

        pending = self._event_buffer.count_pending()
        if not pending:
            return 0

        logger.info(f"Replaying {pending} buffered events")

        def _send(event_type: str, data: dict) -> bool:
            try:
                if event_type == "heartbeat":
                    return self._rest_client.send_heartbeat(data)
                elif event_type == "browser_activity":
                    return self._rest_client.send_browser_event(data)
                elif event_type == "editor_activity":
                    return self._rest_client.send_editor_event(data)
                elif event_type == "metrics":
                    return self._rest_client.send_system_metrics(data)
                return False
            except Exception:
                return False

        self._event_buffer.replay_all(_send)
        return self._event_buffer.count_pending()

    @staticmethod
    def _get_hostname() -> str:
        import socket
        try:
            return socket.gethostname()
        except Exception:
            return "unknown"
