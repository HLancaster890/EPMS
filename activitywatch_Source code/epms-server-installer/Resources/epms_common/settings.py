import os, json, logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("epms.common")

@dataclass
class AppSettings:
    config_path: str = ""
    database: Dict[str, Any] = field(default_factory=lambda: {
        "host": "localhost", "port": 5432, "user": "postgres",
        "password": "", "name": "epms", "max_connections": 10,
    })
    redis: Dict[str, Any] = field(default_factory=lambda: {
        "host": "localhost", "port": 6379, "password": None,
    })
    cors_origins: str = "*"
    trusted_hosts: str = "*"
    service: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: str = None) -> "AppSettings":
        path = config_path or os.environ.get("APP_SETTINGS_PATH", "config/appsettings.json")
        cfg = cls(config_path=path)
        if not os.path.exists(path):
            logger.warning(f"Config not found at {path}, using defaults")
            return cfg
        try:
            with open(path) as f:
                data = json.load(f)
            cfg.database = data.get("database", cfg.database)
            cfg.redis = data.get("redis", cfg.redis)
            cfg.cors_origins = data.get("cors", {}).get("allow_origins", cfg.cors_origins)
            cfg.trusted_hosts = data.get("cors", {}).get("trusted_hosts", cfg.trusted_hosts)
            cfg.service = data.get("services", data.get("service", {}))
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
        return cfg