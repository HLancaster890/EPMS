"""
System tray interface for the EPMS Agent Client.
Provides a tray icon with status indicator, context menu,
and a configuration dialog.
"""

import logging
import threading
from typing import Optional, Callable
from datetime import datetime, timezone

import pystray
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


class SystrayApp:
    """
    System tray application with status icon and context menu.
    Updates icon color based on connection status.
    """

    STATUS_DISCONNECTED = 0
    STATUS_CONNECTING = 1
    STATUS_CONNECTED = 2
    STATUS_ERROR = 3

    def __init__(self, on_quit: Optional[Callable] = None,
                 on_configure: Optional[Callable] = None,
                 on_toggle_monitoring: Optional[Callable] = None):
        self._running = False
        self._status = self.STATUS_DISCONNECTED
        self._status_text = "Disconnected"
        self._last_heartbeat: Optional[str] = None
        self._monitoring_enabled = True
        self._server_host = ""
        self._display_name = ""

        self._on_quit = on_quit
        self._on_configure = on_configure
        self._on_toggle_monitoring = on_toggle_monitoring

        self._icon: Optional[pystray.Icon] = None
        self._menu_items: list = []
        self._thread: Optional[threading.Thread] = None

    def _create_icon_image(self, size: int = 64) -> Image.Image:
        """Create a colored circle icon for the tray."""
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Colors based on status
        colors = {
            self.STATUS_DISCONNECTED: (120, 120, 120),  # Gray
            self.STATUS_CONNECTING: (255, 200, 0),       # Yellow
            self.STATUS_CONNECTED: (0, 180, 80),         # Green
            self.STATUS_ERROR: (200, 40, 40),             # Red
        }
        color = colors.get(self._status, (120, 120, 120))

        # Draw filled circle
        padding = 4
        draw.ellipse(
            [padding, padding, size - padding, size - padding],
            fill=color,
            outline=(255, 255, 255, 200),
            width=2,
        )

        # Draw inner dot for connected status
        if self._status == self.STATUS_CONNECTED:
            inner_color = (0, 255, 0)
            inner_padding = size // 3
            draw.ellipse(
                [inner_padding, inner_padding, size - inner_padding, size - inner_padding],
                fill=inner_color,
            )

        return image

    def _build_menu(self):
        """Build the tray icon context menu."""
        status_label = f"Status: {self._status_text}"
        if self._server_host:
            status_label += f" ({self._server_host})"

        monitoring_label = (
            "Pause Monitoring" if self._monitoring_enabled
            else "Resume Monitoring"
        )

        items = [
            pystray.MenuItem(status_label, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(monitoring_label, self._on_toggle_monitoring_cb),
            pystray.MenuItem("Configure...", self._on_configure_cb),
        ]

        if self._display_name:
            items.append(pystray.Menu.SEPARATOR)
            items.append(
                pystray.MenuItem(f"Agent: {self._display_name}", None, enabled=False)
            )

        if self._last_heartbeat:
            items.append(
                pystray.MenuItem(
                    f"Last heartbeat: {self._last_heartbeat}", None, enabled=False
                )
            )

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Exit", self._on_quit_cb))

        return pystray.Menu(*items)

    def _on_quit_cb(self):
        """Handle quit from tray menu."""
        if self._on_quit:
            self._on_quit()
        self.stop()

    def _on_configure_cb(self):
        """Handle configure from tray menu."""
        if self._on_configure:
            self._on_configure()

    def _on_toggle_monitoring_cb(self):
        """Handle monitoring toggle from tray menu."""
        self._monitoring_enabled = not self._monitoring_enabled
        if self._on_toggle_monitoring:
            self._on_toggle_monitoring(self._monitoring_enabled)
        self.update_menu()

    def update_status(self, status: int, status_text: str = ""):
        """Update the connection status and regenerate icon."""
        self._status = status
        if status_text:
            self._status_text = status_text
        elif status == self.STATUS_DISCONNECTED:
            self._status_text = "Disconnected"
        elif status == self.STATUS_CONNECTING:
            self._status_text = "Connecting..."
        elif status == self.STATUS_CONNECTED:
            self._status_text = "Connected"
        elif status == self.STATUS_ERROR:
            self._status_text = "Error"

        self._update_icon()

    def update_menu(self):
        """Rebuild and set the context menu."""
        if self._icon:
            self._icon.menu = self._build_menu()

    def update_heartbeat_time(self):
        """Update the last heartbeat timestamp."""
        self._last_heartbeat = datetime.now().strftime("%H:%M:%S")
        self.update_menu()

    def set_server_info(self, host: str, display_name: str = ""):
        """Update the server info shown in the menu."""
        self._server_host = host
        self._display_name = display_name
        self.update_menu()

    def _update_icon(self):
        """Regenerate the icon image and update the tray."""
        if self._icon:
            self._icon.icon = self._create_icon_image()
            self.update_menu()

    def start(self):
        """Start the system tray icon in a background thread."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("System tray started")

    def _run(self):
        """Run the tray icon (blocking, called in thread)."""
        icon_image = self._create_icon_image()
        menu = self._build_menu()

        self._icon = pystray.Icon(
            "epms-agent",
            icon_image,
            "EPMS Agent Client",
            menu,
        )
        self._icon.run()

    def stop(self):
        """Stop the system tray icon."""
        self._running = False
        if self._icon:
            self._icon.stop()
            self._icon = None
        logger.info("System tray stopped")


class ConfigDialog:
    """
    Simple configuration dialog using tkinter.
    Allows editing server host, port, API key, display name, and SSL toggle.
    """

    def __init__(self, config_data: dict):
        self._config = config_data
        self._result = None

    def show(self) -> Optional[dict]:
        """Show the configuration dialog and return updated config or None if cancelled."""
        try:
            import tkinter as tk
            from tkinter import ttk
        except ImportError:
            logger.error("tkinter not available, cannot show config dialog")
            return None

        self._result = None
        root = tk.Tk()
        root.title("EPMS Agent Configuration")
        root.geometry("480x380")
        root.resizable(False, False)

        # Make it modal
        root.focus_set()
        root.grab_set()

        frame = ttk.Frame(root, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title = ttk.Label(frame, text="EPMS Agent Configuration",
                          font=("Segoe UI", 14, "bold"))
        title.pack(anchor=tk.W, pady=(0, 15))

        # Server section
        section1 = ttk.Label(frame, text="Server Connection",
                             font=("Segoe UI", 10, "bold"))
        section1.pack(anchor=tk.W, pady=(5, 5))

        # Host
        host_frame = ttk.Frame(frame)
        host_frame.pack(fill=tk.X, pady=2)
        ttk.Label(host_frame, text="Server Host:", width=18, anchor=tk.E).pack(side=tk.LEFT)
        host_var = tk.StringVar(value=self._config.get("server", {}).get("host", ""))
        host_entry = ttk.Entry(host_frame, textvariable=host_var, width=30)
        host_entry.pack(side=tk.LEFT, padx=5)
        host_entry.focus()

        # Port
        port_frame = ttk.Frame(frame)
        port_frame.pack(fill=tk.X, pady=2)
        ttk.Label(port_frame, text="Port:", width=18, anchor=tk.E).pack(side=tk.LEFT)
        port_var = tk.StringVar(value=str(self._config.get("server", {}).get("port", 443)))
        ttk.Entry(port_frame, textvariable=port_var, width=10).pack(side=tk.LEFT, padx=5)

        # API Key
        key_frame = ttk.Frame(frame)
        key_frame.pack(fill=tk.X, pady=2)
        ttk.Label(key_frame, text="API Key:", width=18, anchor=tk.E).pack(side=tk.LEFT)
        key_var = tk.StringVar(value=self._config.get("server", {}).get("api_key", ""))
        key_entry = ttk.Entry(key_frame, textvariable=key_var, width=30, show="*")
        key_entry.pack(side=tk.LEFT, padx=5)

        # SSL
        ssl_frame = ttk.Frame(frame)
        ssl_frame.pack(fill=tk.X, pady=2)
        ttk.Label(ssl_frame, text="Use SSL:", width=18, anchor=tk.E).pack(side=tk.LEFT)
        ssl_var = tk.BooleanVar(value=self._config.get("server", {}).get("use_ssl", True))
        ttk.Checkbutton(ssl_frame, variable=ssl_var).pack(side=tk.LEFT, padx=5)

        # Separator
        ttk.Separator(frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        # Agent section
        section2 = ttk.Label(frame, text="Agent Settings",
                             font=("Segoe UI", 10, "bold"))
        section2.pack(anchor=tk.W, pady=(5, 5))

        # Display Name
        name_frame = ttk.Frame(frame)
        name_frame.pack(fill=tk.X, pady=2)
        ttk.Label(name_frame, text="Display Name:", width=18, anchor=tk.E).pack(side=tk.LEFT)
        name_var = tk.StringVar(value=self._config.get("display_name", ""))
        ttk.Entry(name_frame, textvariable=name_var, width=30).pack(side=tk.LEFT, padx=5)

        # Monitoring interval
        interval_frame = ttk.Frame(frame)
        interval_frame.pack(fill=tk.X, pady=2)
        ttk.Label(interval_frame, text="Heartbeat Interval (s):", width=18, anchor=tk.E).pack(side=tk.LEFT)
        interval_var = tk.StringVar(
            value=str(self._config.get("monitoring", {}).get("heartbeat_interval_seconds", 30))
        )
        ttk.Entry(interval_frame, textvariable=interval_var, width=10).pack(side=tk.LEFT, padx=5)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        def on_save():
            try:
                self._result = {
                    "server": {
                        "host": host_var.get().strip(),
                        "port": int(port_var.get().strip()),
                        "use_ssl": ssl_var.get(),
                        "api_key": key_var.get().strip(),
                    },
                    "monitoring": {
                        "heartbeat_interval_seconds": int(interval_var.get().strip()),
                    },
                    "display_name": name_var.get().strip(),
                }
                root.destroy()
            except ValueError as e:
                import tkinter.messagebox as mb
                mb.showerror("Invalid Input", f"Please check your input: {e}")

        def on_cancel():
            self._result = None
            root.destroy()

        ttk.Button(btn_frame, text="Save", command=on_save, width=12).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=on_cancel, width=12).pack(side=tk.RIGHT)

        root.protocol("WM_DELETE_WINDOW", on_cancel)
        root.mainloop()

        return self._result
