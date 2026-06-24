import logging
import os
from typing import Optional, Union

import tomlkit
from aw_core import dirs
from aw_core.config import load_config_toml

logger = logging.getLogger(__name__)

default_config = """
[server]
hostname = "127.0.0.1"
port = "5600"

[client]
commit_interval = 10

[server-testing]
hostname = "127.0.0.1"
port = "5666"

[client-testing]
commit_interval = 5
""".strip()


def load_config():
    return load_config_toml("aw-client", default_config)


def load_local_server_api_key(host: str, port: Union[int, str]) -> Optional[str]:
    """Load the API key for connecting to a given server.

    Resolution order:
    1. If connecting to localhost, read from aw-server-rust's config.toml (legacy)
    2. If an 'api_key' is set in the [server] section of aw-client.toml, use it
       (works for both local and remote servers)
    3. Look for a per-host key in a [server.<host>] section of aw-client.toml

    Returns None if no key is configured.
    """
    try:
        requested_port = int(str(port))
    except (TypeError, ValueError):
        requested_port = 5600

    # First, try the aw-client.toml config for a per-server api_key
    client_config = load_config()
    server_key = client_config.get("server", {}).get("api_key")
    if server_key:
        return str(server_key)

    # Next, try a per-host section: [server.<host>]
    host_key = host.replace(".", "_").replace("-", "_")
    per_host_key = client_config.get(f"server.{host_key}", {}).get("api_key")
    if per_host_key:
        return str(per_host_key)

    # For localhost, fall back to aw-server-rust's config (legacy behavior)
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return None

    config_dir = dirs.get_config_dir("aw-server-rust")
    candidates = (
        ("config.toml", 5600),
        ("config-testing.toml", 5666),
    )

    for filename, default_port in candidates:
        config_path = os.path.join(config_dir, filename)
        if not os.path.isfile(config_path):
            continue

        try:
            with open(config_path, encoding="utf-8") as f:
                config = tomlkit.parse(f.read())
            configured_port = int(str(config.get("port", default_port)))
            if configured_port != requested_port:
                continue

            auth_config = config.get("auth", {})
            api_key = auth_config.get("api_key")
            if api_key:
                return str(api_key)
        except Exception as e:
            logger.warning(
                "Failed to read aw-server-rust config %s: %s", config_path, e
            )

    return None
