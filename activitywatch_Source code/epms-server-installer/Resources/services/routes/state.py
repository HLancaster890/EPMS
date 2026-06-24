import os
import json
import time as time_mod
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from asyncio import Lock
from fastapi import WebSocket
import asyncpg

logger = logging.getLogger("epms.server")

db_pool: Optional[asyncpg.Pool] = None
redis_client = None
start_time = datetime.now(timezone.utc)
_API_KEY_PEPPER = ""

CONFIG_PATH = os.environ.get("APP_SETTINGS_PATH", "config/appsettings.json")


class WSConnectionManager:
    def __init__(self):
        self.agent_connections: Dict[str, Dict[str, Any]] = {}
        self.dashboard_connections: Dict[str, WebSocket] = {}
        self._lock = Lock()

    @property
    def agent_count(self) -> int:
        return len(self.agent_connections)

    @property
    def dashboard_count(self) -> int:
        return len(self.dashboard_connections)

    async def connect_agent(self, agent_id: str, websocket: WebSocket, info: Dict[str, Any]):
        async with self._lock:
            if agent_id in self.agent_connections:
                old_ws = self.agent_connections[agent_id]["websocket"]
                try:
                    await old_ws.close(code=1000, reason="Replaced")
                except Exception:
                    pass
            self.agent_connections[agent_id] = {
                "websocket": websocket, "agent_info": info,
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "last_message": time_mod.time(), "message_count": 0,
            }

    async def disconnect_agent(self, agent_id: str):
        async with self._lock:
            self.agent_connections.pop(agent_id, None)

    async def connect_dashboard(self, session_id: str, websocket: WebSocket):
        async with self._lock:
            self.dashboard_connections[session_id] = websocket

    async def disconnect_dashboard(self, session_id: str):
        async with self._lock:
            self.dashboard_connections.pop(session_id, None)

    async def broadcast_to_dashboards(self, event_type: str, data: Dict[str, Any]):
        payload = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now(timezone.utc).isoformat()})
        async with self._lock:
            disconnected = []
            for sid, ws in self.dashboard_connections.items():
                try:
                    await ws.send_text(payload)
                except Exception:
                    disconnected.append(sid)
            for sid in disconnected:
                self.dashboard_connections.pop(sid, None)

    async def send_to_agent(self, agent_id: str, message: Dict[str, Any]) -> bool:
        async with self._lock:
            conn = self.agent_connections.get(agent_id)
            if conn:
                try:
                    await conn["websocket"].send_text(json.dumps(message))
                    return True
                except Exception:
                    self.agent_connections.pop(agent_id, None)
            return False

    async def update_last_message(self, agent_id: str):
        async with self._lock:
            conn = self.agent_connections.get(agent_id)
            if conn:
                conn["last_message"] = time_mod.time()
                conn["message_count"] += 1


ws_manager = WSConnectionManager()