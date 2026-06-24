#!/usr/bin/env python3
"""
EPMS Enterprise Productivity Monitor
Continuous monitoring mode: starts gateway, connects agent, streams productivity data.

Run: python monitor-productivity.py
This will:
  1. Start the Gateway Server on port 8005
  2. Connect an Agent Client
  3. Stream live heartbeats with productivity metrics
  4. Display AFK status, activity tracking, and system health
"""

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
RELEASE_DIR = SCRIPT_DIR.parent
CONFIG_DIR = RELEASE_DIR / "config"
LOG_DIR = RELEASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Color formatting for terminal output ──────────────────────────
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    CLEAR_LINE = "\033[K"

# ── Shared state ──────────────────────────────────────────────────
running = True
server_process = None
stats = {
    "heartbeats_sent": 0,
    "heartbeats_ack": 0,
    "errors": 0,
    "start_time": time.time(),
}

def signal_handler(signum, frame):
    global running
    print(f"\n{Colors.YELLOW}Shutting down...{Colors.RESET}")
    running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def start_gateway():
    """Start the gateway server in a subprocess."""
    global server_process
    config_file = CONFIG_DIR / "gateway.json"
    log_file = LOG_DIR / "gateway-monitor.log"

    cmd = [
        sys.executable, "-m", "epms_gateway",
        "--config", str(config_file),
        "--log-level", "INFO",
    ]

    try:
        with open(log_file, "w") as lf:
            server_process = subprocess.Popen(
                cmd,
                stdout=lf,
                stderr=subprocess.STDOUT,
                text=True,
            )
        return True
    except Exception as e:
        print(f"  {Colors.RED}Failed to start gateway: {e}{Colors.RESET}")
        return False


def stop_gateway():
    """Stop the gateway server."""
    global server_process
    if server_process:
        try:
            server_process.terminate()
            server_process.wait(timeout=5)
        except Exception:
            try:
                server_process.kill()
            except Exception:
                pass
        server_process = None


def monitor_loop():
    """Main monitoring loop: connect to gateway and stream heartbeats."""
    global running

    # Import agent modules (must be installed via pip install -e .)
    from epms_agent.api_client import EPMSApiClient
    from epms_agent.config import load_config
    from epms_agent.monitor import get_heartbeat_data, get_afk_seconds, get_active_window_info

    config = load_config(str(CONFIG_DIR / "agent.json"))
    client = EPMSApiClient(config)

    heartbeat_interval = config.monitoring.heartbeat_interval_seconds
    last_status_update = 0

    # Wait for gateway to be ready
    time.sleep(2)

    print(f"\n{Colors.BOLD}{Colors.CYAN}── Connecting to EPMS Gateway ──{Colors.RESET}\n")

    # Health check (optional - REST API may not be running)
    rest_available = client.health_check()
    if not rest_available:
        print(f"  {Colors.YELLOW}REST API not available (running in gateway-only mode){Colors.RESET}")
    else:
        print(f"  {Colors.GREEN}REST API reachable{Colors.RESET}")

    # Register agent via REST (if available)
    if rest_available:
        if not client.register_agent(config.display_name or "Monitor"):
            print(f"  {Colors.YELLOW}Registration warning - continuing anyway{Colors.RESET}")

    # Connect WebSocket
    client.connect_websocket()
    time.sleep(1)

    print(f"{Colors.BOLD}{Colors.GREEN}Connected! Streaming productivity data...{Colors.RESET}")
    print(f"{'─' * 70}")

    try:
        while running:
            cycle_start = time.time()

            # ── Collect and send heartbeat ────────────────────────
            try:
                hb = get_heartbeat_data(config.monitoring.afk_timeout_minutes)
                result = client.send_heartbeat(config.monitoring.afk_timeout_minutes)
                stats["heartbeats_sent"] += 1
                if result:
                    stats["heartbeats_ack"] += 1
                else:
                    stats["errors"] += 1
            except Exception as e:
                stats["errors"] += 1
                logging.debug(f"Heartbeat error: {e}")

            # ── Live status display ───────────────────────────────
            now = time.time()
            if now - last_status_update >= 2.0:  # Update display every 2s
                last_status_update = now
                uptime = int(now - stats["start_time"])
                active_win = get_active_window_info()
                afk_secs = get_afk_seconds()
                is_afk = afk_secs > (config.monitoring.afk_timeout_minutes * 60)

                # Clear and redraw status
                print(f"\033[F\033[J", end="")  # Move up and clear
                print(f"{Colors.BOLD}{Colors.CYAN}EPMS Enterprise Productivity Monitor{Colors.RESET}")
                print(f"{'─' * 70}")
                print(f"  Uptime:        {uptime // 3600:02d}:{(uptime % 3600) // 60:02d}:{uptime % 60:02d}")
                print(f"  Heartbeats:    {stats['heartbeats_sent']} sent, {stats['heartbeats_ack']} acked")
                print(f"  Errors:        {stats['errors']}")
                print(f"  Status:        {Colors.GREEN if client.is_connected else Colors.RED}{'Connected' if client.is_connected else 'Disconnected'}{Colors.RESET}")

                # Active window
                title = active_win.get("title", "N/A")
                print(f"  Active Window: {title[:60]}{'..' if len(title) > 60 else ''}")

                # AFK status
                afk_color = Colors.RED if is_afk else Colors.GREEN
                print(f"  AFK Status:    {afk_color}{'AFK' if is_afk else 'Active'}{Colors.RESET} ({afk_secs:.0f}s idle)")

                # Browser/Editor activity
                browser = hb.get("browser_activity")
                editor = hb.get("editor_activity")
                if browser:
                    print(f"  Browser:       {browser.get('browser_name', '?')} - {browser.get('domain', '?')}")
                    if browser.get("is_productive"):
                        print(f"  Productivity:  {Colors.GREEN}Productive{Colors.RESET}")
                    else:
                        print(f"  Productivity:  {Colors.RED}Distracting{Colors.RESET}")
                if editor:
                    print(f"  Editor:        {editor.get('editor_name', '?')} - {editor.get('language', '?')}")

                # Heartbeat countdown
                remaining = max(0, heartbeat_interval - (now - cycle_start))
                bar_len = 30
                filled = int((heartbeat_interval - remaining) / heartbeat_interval * bar_len) if heartbeat_interval > 0 else 0
                bar = "█" * filled + "░" * (bar_len - filled)
                print(f"  Next HB:       [{bar}] {remaining:.0f}s")
                print(f"{'─' * 70}")
                print(f"  {Colors.YELLOW}Press Ctrl+C to stop monitoring{Colors.RESET}")
                print(f"\033[F\033[J", end="")  # Move up and clear for next update

            # ── Sleep until next cycle ─────────────────────────────
            elapsed = time.time() - cycle_start
            sleep_time = max(0.1, min(heartbeat_interval - elapsed, 1.0))
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect_websocket()
        print(f"\n{Colors.BOLD}{Colors.GREEN}Monitoring stopped.{Colors.RESET}")
        print(f"  Heartbeats: {stats['heartbeats_sent']} sent, {stats['heartbeats_ack']} acked")
        print(f"  Duration:   {int(time.time() - stats['start_time'])}s")
        print(f"  Errors:     {stats['errors']}")


def main():
    """Main entry point - start gateway + monitor."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  EPMS Enterprise Productivity Monitor v1.0.0{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 60}{Colors.RESET}")
    print(f"  Starting Gateway Server...")

    if not start_gateway():
        print(f"  {Colors.RED}Failed to start gateway server{Colors.RESET}")
        sys.exit(1)

    time.sleep(2)

    try:
        monitor_loop()
    finally:
        stop_gateway()
        print(f"\n  Gateway server stopped.")


if __name__ == "__main__":
    main()
