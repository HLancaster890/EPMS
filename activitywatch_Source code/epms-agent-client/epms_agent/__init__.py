"""
EPMS Agent Client — Desktop monitoring agent for EPMS Enterprise Server.
Connects to the EPMS server via API key authentication and reports
activity data, system metrics, and heartbeats.
"""

__version__ = "1.0.0.0"
__app_name__ = "EPMS Agent Client"
__author__ = "EPMS Inc."

# Default paths
import os
from pathlib import Path

APP_DATA_DIR = Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "EPMS" / "Agent"
CONFIG_DIR = APP_DATA_DIR / "config"
LOG_DIR = APP_DATA_DIR / "logs"
BUFFER_DIR = APP_DATA_DIR / "buffer"
CONFIG_FILE = CONFIG_DIR / "agent.json"
