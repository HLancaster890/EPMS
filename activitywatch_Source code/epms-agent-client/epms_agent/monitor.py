"""
Process and system monitoring for the EPMS Agent Client.
Scans ALL running processes every heartbeat via psutil,
tracks foreground window, AFK status, and system metrics.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import psutil

logger = logging.getLogger(__name__)

try:
    import win32gui
    import win32api
    import win32process
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False
    logger.warning("pywin32 not available, window/foreground tracking disabled")

from .browser_monitor import is_browser_process, get_browser_activity_data
from .editor_monitor import is_editor_process, get_editor_activity_data


# Cache foreground PID between scans for session continuity
_last_foreground_pid: Optional[int] = None
_last_foreground_name: Optional[str] = None


def get_foreground_window_info() -> Dict[str, Any]:
    """Get info about the currently focused window."""
    if not HAS_WIN32:
        return {"title": "", "process_name": "", "pid": 0, "executable": ""}
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return {"title": "", "process_name": "", "pid": 0, "executable": ""}
        title = win32gui.GetWindowText(hwnd)
        pid = win32process.GetWindowThreadProcessId(hwnd)[1]
        try:
            proc = psutil.Process(pid)
            pname = proc.name()
            exe = proc.exe()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pname = "unknown"
            exe = ""
        return {"title": title, "process_name": pname, "pid": pid, "executable": exe}
    except Exception as e:
        logger.debug("Error getting foreground window: %s", e)
        return {"title": "", "process_name": "", "pid": 0, "executable": ""}


def scan_all_processes() -> List[Dict[str, Any]]:
    """Return a snapshot of every running process on the system."""
    processes: List[Dict[str, Any]] = []
    for proc in psutil.process_iter(["pid", "name", "exe", "cpu_percent",
                                      "memory_percent", "username", "cmdline",
                                      "ppid", "create_time"]):
        try:
            pinfo = proc.info
            processes.append({
                "pid": pinfo["pid"],
                "ppid": pinfo["ppid"] or 0,
                "process_name": pinfo["name"] or "",
                "process_path": pinfo["exe"] or "",
                "cpu_percent": round(pinfo["cpu_percent"] or 0, 1),
                "memory_percent": round(pinfo["memory_percent"] or 0, 2),
                "username": pinfo["username"] or "",
                "cmd_line": " ".join(pinfo["cmdline"]) if pinfo.get("cmdline") else "",
                "create_time": pinfo["create_time"] or 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
            pass
    return processes


def get_last_input_time() -> Optional[float]:
    """Get timestamp of last user input (keyboard/mouse)."""
    if not HAS_WIN32:
        return None
    try:
        last_input_info = win32api.GetLastInputInfo()
        current_ticks = win32api.GetTickCount()
        if hasattr(last_input_info, "dwTime"):
            last_ticks = last_input_info.dwTime
        elif isinstance(last_input_info, (tuple, list)):
            last_ticks = last_input_info[-1]
        else:
            last_ticks = last_input_info
        idle_ms = current_ticks - last_ticks
        return time.time() - (idle_ms / 1000.0)
    except Exception as e:
        logger.debug("Error getting last input time: %s", e)
        return None


def get_afk_seconds(afk_timeout_minutes: int = 5) -> float:
    last_input = get_last_input_time()
    if last_input is None:
        return 0.0
    return time.time() - last_input


def is_user_afk(afk_timeout_minutes: int = 5) -> bool:
    return get_afk_seconds(afk_timeout_minutes) > (afk_timeout_minutes * 60)


def get_system_info() -> Dict[str, Any]:
    """Collect system health and performance metrics."""
    try:
        cpu_percent = psutil.cpu_percent(interval=0.3)
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
                "frequency_mhz": cpu_freq.current if cpu_freq else 0,
            },
            "memory": {
                "total_gb": round(memory.total / (1024 ** 3), 2),
                "available_gb": round(memory.available / (1024 ** 3), 2),
                "percent": memory.percent,
            },
            "disk": {
                "total_gb": round(disk.total / (1024 ** 3), 2),
                "free_gb": round(disk.free / (1024 ** 3), 2),
                "percent": disk.percent,
            },
            "network": {
                "bytes_sent_mb": round(net.bytes_sent / (1024 ** 2), 2),
                "bytes_recv_mb": round(net.bytes_recv / (1024 ** 2), 2),
            },
            "uptime_seconds": int(time.time() - psutil.boot_time()),
            "os": "Windows",
        }
    except Exception as e:
        logger.error("Error getting system info: %s", e)
        return {"error": str(e)}


def get_heartbeat_data(afk_timeout_minutes: int = 5) -> Dict[str, Any]:
    """Collect full monitoring snapshot for one heartbeat cycle."""
    global _last_foreground_pid, _last_foreground_name

    foreground = get_foreground_window_info()
    fg_pid = foreground.get("pid", 0)
    fg_process = foreground.get("process_name", "")
    title = foreground.get("title", "")

    # Update foreground continuity cache
    if fg_pid and fg_pid != _last_foreground_pid:
        _last_foreground_pid = fg_pid
        _last_foreground_name = fg_process
    foreground_name = _last_foreground_name or fg_process

    afk_seconds = get_afk_seconds(afk_timeout_minutes)
    system = get_system_info()

    # Enrich foreground activity
    browser_activity = get_browser_activity(title, foreground_name)
    editor_activity = get_editor_activity(title, foreground_name)

    # Full process scan
    processes = scan_all_processes()

    # Mark the foreground PID in each process entry
    for p in processes:
        if p["pid"] == fg_pid:
            p["is_foreground"] = True
            p["window_title"] = title
        else:
            p["is_foreground"] = False
            p["window_title"] = ""

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "foreground_window": foreground,
        "browser_activity": browser_activity or None,
        "editor_activity": editor_activity or None,
        "afk_seconds": round(afk_seconds, 1),
        "is_afk": afk_seconds > (afk_timeout_minutes * 60),
        "system": system,
        "processes": processes,
    }
