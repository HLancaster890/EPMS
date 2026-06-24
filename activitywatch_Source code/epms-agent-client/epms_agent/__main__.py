"""
EPMS Agent Client — Main entry point.
Connects to EPMS server, monitors activity, and runs in system tray.
Includes signal handlers for graceful shutdown on SIGTERM/SIGINT.
"""

import argparse
import logging
import logging.handlers
import os
import signal
import sys
import time
import threading
from pathlib import Path
from typing import Optional

# PyInstaller compatibility: when run as a standalone executable,
# __package__ is None and relative imports fail.
# We fall back to adding the parent dir to sys.path.
if __package__ is None:
    import sys as _sys
    from pathlib import Path as _Path
    _pkg_dir = str(_Path(__file__).resolve().parent.parent)
    if _pkg_dir not in _sys.path:
        _sys.path.insert(0, _pkg_dir)
    from epms_agent import __version__, __app_name__, LOG_DIR
    from epms_agent.config import load_config, save_config, AgentConfig
    from epms_agent.api_client import EPMSApiClient
    from epms_agent.systray import SystrayApp, ConfigDialog
    from epms_agent.monitor import get_heartbeat_data
else:
    from . import __version__, __app_name__, LOG_DIR
    from .config import load_config, save_config, AgentConfig
    from .api_client import EPMSApiClient
    from .systray import SystrayApp, ConfigDialog
    from .monitor import get_heartbeat_data

logger = logging.getLogger(__name__)

# Global reference for signal handler
_app_instance: Optional['AgentApplication'] = None


def _signal_handler(signum, frame):
    """Handle OS signals for graceful shutdown."""
    signal_name = signal.Signals(signum).name
    logger.info(f"Received signal {signal_name}, shutting down gracefully...")
    if _app_instance:
        _app_instance.stop()


def setup_logging(verbose: bool = False):
    """Configure logging to file and console."""
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "agent.log"

    level = logging.DEBUG if verbose else logging.INFO

    # File handler (rotating, keep 5MB * 3)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    logger.info(f"{__app_name__} v{__version__} starting")
    logger.info(f"Log file: {log_file}")


class AgentApplication:
    """Main application controller for the EPMS Agent."""

    def __init__(self, config: AgentConfig, no_tray: bool = False):
        self.config = config
        self._no_tray = no_tray
        self._running = False
        self._monitoring_enabled = True
        self._api_client = EPMSApiClient(config)
        self._systray: Optional[SystrayApp] = None

        # Threads
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._reconnect_thread: Optional[threading.Thread] = None

    def start(self):
        """Start the agent application."""
        global _app_instance
        _app_instance = self

        # Register signal handlers for graceful shutdown
        # SIGTERM is not available on Windows; skip gracefully
        for sig in (signal.SIGINT,):
            try:
                signal.signal(sig, _signal_handler)
            except (ValueError, AttributeError):
                pass
        try:
            signal.signal(signal.SIGTERM, _signal_handler)
        except (ValueError, AttributeError):
            pass

        self._running = True

        # Start system tray (unless --no-tray)
        if not self._no_tray:
            self._start_systray()

        # Start monitoring threads
        self._start_background_threads()

        logger.info(f"Agent started, connecting to {self.config.server_url}")
        self._update_status(SystrayApp.STATUS_CONNECTING, "Connecting...")

        # Initial connection attempt
        self._attempt_connection()

        # Keep main thread alive until _running becomes False (via signal or error)
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.stop()
        finally:
            _app_instance = None

    def stop(self):
        """Stop the agent application."""
        self._running = False
        if self._systray:
            self._systray.stop()
        logger.info("Agent stopped")

    def _start_systray(self):
        """Initialize and start the system tray app."""
        self._systray = SystrayApp(
            on_quit=self.stop,
            on_configure=self._show_config_dialog,
            on_toggle_monitoring=self._toggle_monitoring,
        )
        self._systray.set_server_info(
            host=self.config.server.host,
            display_name=self.config.display_name,
        )
        self._systray.start()

    def _start_background_threads(self):
        """Start heartbeat and reconnect threads."""
        # Initialize REST client early
        self._api_client.connect_rest()

        # Heartbeat thread
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        # Reconnect thread
        self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self._reconnect_thread.start()

    def _update_status(self, status: int, text: str = ""):
        """Update the system tray status."""
        if self._systray:
            self._systray.update_status(status, text)

    def _attempt_connection(self) -> bool:
        """Try to connect to the EPMS server via REST."""
        logger.info(f"Attempting to connect to {self.config.server_url}...")

        if not self._api_client.health_check():
            logger.warning("Server health check failed")
            self._update_status(SystrayApp.STATUS_DISCONNECTED, "Server unreachable")
            return False

        # Register agent with server
        if not self._api_client.register_agent(self.config.display_name):
            logger.warning("Agent registration failed")
            self._update_status(SystrayApp.STATUS_ERROR, "Registration failed")
            return False

        self._update_status(SystrayApp.STATUS_CONNECTED, "Connected")
        logger.info("Successfully connected and registered with server")
        return True

    def _heartbeat_loop(self):
        """Periodically send heartbeats to the server.

        Heartbeats are always collected and dispatched. When the WebSocket is
        connected they are sent immediately; when offline they are buffered
        to a local SQLite database for replay on reconnect. No data is lost.
        """
        interval = self.config.monitoring.heartbeat_interval_seconds

        while self._running:
            time.sleep(interval)

            if not self._monitoring_enabled:
                continue

            try:
                ok = self._api_client.send_heartbeat(
                    self.config.monitoring.afk_timeout_minutes
                )
                if ok and self._systray:
                    self._systray.update_heartbeat_time()
                elif not ok and self._systray:
                    # Show buffered count in systray tooltip
                    try:
                        count = self._api_client._event_buffer.count_pending() if self._api_client._event_buffer else 0
                        if count:
                            self._systray.update_status(
                                SystrayApp.STATUS_CONNECTING,
                                f"Offline ({count} buffered)"
                            )
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Error sending heartbeat: {e}")

    def _reconnect_loop(self):
        """Periodically attempt to reconnect if connection is lost."""
        while self._running:
            time.sleep(30)

            if not self._api_client.is_connected:
                logger.info("Attempting to reconnect...")
                self._update_status(SystrayApp.STATUS_CONNECTING, "Reconnecting...")
                if self._attempt_connection():
                    logger.info("Reconnected successfully")
                else:
                    self._update_status(SystrayApp.STATUS_DISCONNECTED, "Disconnected")

    def _toggle_monitoring(self, enabled: bool):
        """Toggle monitoring on/off from tray menu."""
        self._monitoring_enabled = enabled
        status = "Monitoring enabled" if enabled else "Monitoring paused"
        logger.info(status)
        if enabled:
            self._update_status(
                SystrayApp.STATUS_CONNECTED if self._api_client.is_connected
                else SystrayApp.STATUS_DISCONNECTED,
                status
            )
        else:
            self._update_status(SystrayApp.STATUS_CONNECTED, status)

    def _show_config_dialog(self):
        """Show the configuration dialog and apply changes."""
        config_data = {
            "server": {
                "host": self.config.server.host,
                "port": self.config.server.port,
                "use_ssl": self.config.server.use_ssl,
                "api_key": self.config.server.api_key,
            },
            "monitoring": {
                "heartbeat_interval_seconds": self.config.monitoring.heartbeat_interval_seconds,
            },
            "display_name": self.config.display_name,
        }

        dialog = ConfigDialog(config_data)
        result = dialog.show()

        if result:
            # Apply new settings
            self.config.server.host = result["server"]["host"]
            self.config.server.port = result["server"]["port"]
            self.config.server.use_ssl = result["server"]["use_ssl"]
            self.config.server.api_key = result["server"]["api_key"]
            self.config.monitoring.heartbeat_interval_seconds = result["monitoring"]["heartbeat_interval_seconds"]
            self.config.display_name = result["display_name"]

            save_config(self.config)

            # Recreate API client with new config
            self._api_client = EPMSApiClient(self.config)

            if self._systray:
                self._systray.set_server_info(
                    host=self.config.server.host,
                    display_name=self.config.display_name,
                )

            # Try connecting with new settings
            self._update_status(SystrayApp.STATUS_CONNECTING, "Reconnecting...")
            self._attempt_connection()

            logger.info("Configuration updated")
            print(f"Configuration saved. Connecting to {self.config.server_url}")


def main():
    """Main entry point for the EPMS Agent Client."""
    parser = argparse.ArgumentParser(
        description="EPMS Agent Client — Desktop monitoring agent"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to configuration file",
        default=None,
    )
    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="Run without system tray (console mode)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    # Single-run commands
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check connection to server and exit",
    )
    parser.add_argument(
        "--oneshot",
        action="store_true",
        help="Send one heartbeat and exit",
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # Load config
    config = load_config(args.config)

    if args.check:
        # Just check connection and exit
        client = EPMSApiClient(config)
        if client.health_check():
            print(f"✓ Server at {config.server_url} is reachable")
            if client.register_agent(config.display_name):
                print(f"✓ Agent registered successfully")
            sys.exit(0)
        else:
            print(f"✗ Server at {config.server_url} is NOT reachable")
            sys.exit(1)

    if args.oneshot:
        # Send one heartbeat and exit
        client = EPMSApiClient(config)
        if client.health_check():
            client.register_agent(config.display_name)
            heartbeat = get_heartbeat_data()
            print(f"Heartbeat data: {heartbeat}")
            if client.send_heartbeat():
                print("✓ Heartbeat sent successfully")
                sys.exit(0)
            else:
                print("✗ Failed to send heartbeat")
                sys.exit(1)
        else:
            print(f"✗ Cannot connect to server at {config.server_url}")
            sys.exit(1)

    # Run the application
    app = AgentApplication(config, no_tray=args.no_tray)
    app.start()


if __name__ == "__main__":
    main()
