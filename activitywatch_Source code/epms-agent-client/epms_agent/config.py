"""
Configuration management for the EPMS Agent Client.
Reads/writes agent.json config file with server connection details.
"""

import json
import os
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from . import CONFIG_FILE, CONFIG_DIR, BUFFER_DIR

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "server": {
        "host": "127.0.0.1",
        "port": 8000,
        "use_ssl": False,
        "api_key": "",
    },
    "monitoring": {
        "enabled": True,
        "heartbeat_interval_seconds": 30,
        "system_info_interval_seconds": 300,
        "activity_monitor_interval_seconds": 5,
        "afk_timeout_minutes": 5,
    },
    "buffer": {
        "enabled": True,
        "max_events": 10000,
        "max_age_days": 7,
    },
    "display_name": "",
    "auto_start": True,
}


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8000
    use_ssl: bool = False
    api_key: str = ""

    def __post_init__(self):
        """Validate port ranges after initialization."""
        if not (1 <= self.port <= 65535):
            logger.warning(f"Invalid server port {self.port}, defaulting to 8000")
            self.port = 8000
        if not self.host:
            logger.warning("Empty server host, defaulting to 127.0.0.1")
            self.host = "127.0.0.1"


@dataclass
class MonitoringConfig:
    enabled: bool = True
    heartbeat_interval_seconds: int = 30
    system_info_interval_seconds: int = 300
    activity_monitor_interval_seconds: int = 5
    afk_timeout_minutes: int = 5

    def __post_init__(self):
        """Validate monitoring intervals after initialization."""
        if self.heartbeat_interval_seconds < 5:
            logger.warning(f"heartbeat_interval_seconds too low ({self.heartbeat_interval_seconds}), setting to 5")
            self.heartbeat_interval_seconds = 5
        if self.heartbeat_interval_seconds > 3600:
            logger.warning(f"heartbeat_interval_seconds too high ({self.heartbeat_interval_seconds}), setting to 3600")
            self.heartbeat_interval_seconds = 3600
        if self.afk_timeout_minutes < 1:
            self.afk_timeout_minutes = 1
        if self.afk_timeout_minutes > 1440:
            self.afk_timeout_minutes = 1440


@dataclass
class BufferConfig:
    enabled: bool = True
    max_events: int = 10000
    max_age_days: int = 7

    def __post_init__(self):
        if self.max_events < 100:
            logger.warning(f"max_events too low ({self.max_events}), setting to 100")
            self.max_events = 100
        if self.max_events > 100000:
            logger.warning(f"max_events too high ({self.max_events}), setting to 100000")
            self.max_events = 100000
        if self.max_age_days < 1:
            self.max_age_days = 1
        if self.max_age_days > 90:
            self.max_age_days = 90

    @property
    def db_path(self) -> str:
        return str(BUFFER_DIR / "events.db")


@dataclass
class AgentConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    buffer: BufferConfig = field(default_factory=BufferConfig)
    display_name: str = ""
    auto_start: bool = True
    agent_id: str = ""

    @property
    def server_url(self) -> str:
        protocol = "https" if self.server.use_ssl else "http"
        return f"{protocol}://{self.server.host}:{self.server.port}"

    @property
    def agent_api_url(self) -> str:
        return f"{self.server_url}/api/v1/agent"


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """Load configuration from JSON file, creating with defaults if not found."""
    path = Path(config_path) if config_path else CONFIG_FILE

    try:
        if path.exists():
            with open(path, "r") as f:
                data = json.load(f)
            return _dict_to_config(data)
        else:
            logger.info(f"Config file not found at {path}, creating defaults")
            config = AgentConfig()
            save_config(config, path)
            return config
    except Exception as e:
        logger.warning(f"Failed to load config from {path}: {e}, using defaults")
        return AgentConfig()


def save_config(config: AgentConfig, config_path: Optional[str] = None) -> None:
    """Save configuration to JSON file."""
    path = Path(config_path) if config_path else CONFIG_FILE

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = _config_to_dict(config)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Configuration saved to {path}")
    except Exception as e:
        logger.error(f"Failed to save config to {path}: {e}")


def _dict_to_config(data: dict) -> AgentConfig:
    """Convert a dictionary to AgentConfig dataclass."""
    server_data = data.get("server", {})
    monitoring_data = data.get("monitoring", {})
    buffer_data = data.get("buffer", {})

    return AgentConfig(
        server=ServerConfig(
            host=server_data.get("host", "127.0.0.1"),
            port=server_data.get("port", 443),
            use_ssl=server_data.get("use_ssl", True),
            api_key=server_data.get("api_key", ""),

        ),
        monitoring=MonitoringConfig(
            enabled=monitoring_data.get("enabled", True),
            heartbeat_interval_seconds=monitoring_data.get("heartbeat_interval_seconds", 30),
            system_info_interval_seconds=monitoring_data.get("system_info_interval_seconds", 300),
            activity_monitor_interval_seconds=monitoring_data.get("activity_monitor_interval_seconds", 5),
            afk_timeout_minutes=monitoring_data.get("afk_timeout_minutes", 5),
        ),
        buffer=BufferConfig(
            enabled=buffer_data.get("enabled", True),
            max_events=buffer_data.get("max_events", 10000),
            max_age_days=buffer_data.get("max_age_days", 7),
        ),
        display_name=data.get("display_name", ""),
        auto_start=data.get("auto_start", True),
        agent_id=data.get("agent_id", ""),
    )


def _config_to_dict(config: AgentConfig) -> dict:
    """Convert AgentConfig dataclass to a dictionary."""
    return {
        "server": {
            "host": config.server.host,
            "port": config.server.port,
            "use_ssl": config.server.use_ssl,
            "api_key": config.server.api_key,

        },
        "monitoring": {
            "enabled": config.monitoring.enabled,
            "heartbeat_interval_seconds": config.monitoring.heartbeat_interval_seconds,
            "system_info_interval_seconds": config.monitoring.system_info_interval_seconds,
            "activity_monitor_interval_seconds": config.monitoring.activity_monitor_interval_seconds,
            "afk_timeout_minutes": config.monitoring.afk_timeout_minutes,
        },
        "buffer": {
            "enabled": config.buffer.enabled,
            "max_events": config.buffer.max_events,
            "max_age_days": config.buffer.max_age_days,
        },
        "display_name": config.display_name,
        "auto_start": config.auto_start,
        "agent_id": config.agent_id,
    }
