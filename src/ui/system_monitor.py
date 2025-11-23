"""
System Monitor Widget for LocalScribe

Real-time CPU and RAM monitoring with color-coded status indicators.
"""

import customtkinter as ctk
import psutil
import platform
import threading
from typing import Optional, Callable


class SystemMonitor(ctk.CTkFrame):
    """
    Real-time system resource monitor with color-coded indicators.

    Color scheme (user thresholds):
    - 0-74%: Green (healthy)
    - 75-84%: Yellow (elevated)
    - 85-90%: Orange (high)
    - 90%+: Red (critical)
    - 100%: Red with exclamation mark
    """

    def __init__(self, parent=None, update_interval_ms=1000):
        """
        Initialize the system monitor.

        Args:
            parent: Parent widget
            update_interval_ms: Update frequency in milliseconds (default 1000)
        """
        super().__init__(parent, fg_color="transparent")
        self.update_interval_ms = update_interval_ms
        self.monitoring = False
        self.tooltip_window = None
        self.show_timer = None

        # Get CPU info
        try:
            self.cpu_model = platform.processor() or "Unknown CPU"
        except Exception:
            self.cpu_model = "Unknown CPU"

        self.physical_cores = psutil.cpu_count(logical=False) or 1
        self.logical_cores = psutil.cpu_count(logical=True) or 1

        # Create label for display
        self.monitor_label = ctk.CTkLabel(
            self,
            text="CPU: 0% | RAM: 0.0/0.0 GB",
            font=ctk.CTkFont(size=10),
            text_color="white"
        )
        self.monitor_label.pack(padx=10, pady=5)

        # Bind tooltip events
        self.monitor_label.bind("<Enter>", self._on_enter)
        self.monitor_label.bind("<Leave>", self._on_leave)

        # Start monitoring thread
        self.start_monitoring()

    def start_monitoring(self):
        """Start the monitoring thread."""
        self.monitoring = True
        thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        thread.start()

    def stop_monitoring(self):
        """Stop the monitoring thread."""
        self.monitoring = False

    def _monitoring_loop(self):
        """Background thread that updates metrics."""
        while self.monitoring:
            try:
                self._update_display()
                # Use after instead of sleep to check stop condition more responsively
                self.after(self.update_interval_ms)
            except Exception as e:
                print(f"Monitor error: {e}")

    def _update_display(self):
        """Update the display with current system metrics."""
        try:
            # Get current metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            ram_used_gb = memory.used / (1024 ** 3)
            ram_total_gb = memory.total / (1024 ** 3)

            # Format display text
            cpu_indicator = "!" if cpu_percent >= 100 else ""
            display_text = f"CPU: {cpu_percent:.0f}%{cpu_indicator} | RAM: {ram_used_gb:.1f}/{ram_total_gb:.1f} GB"

            # Get colors based on thresholds
            bg_color, fg_color = self._get_colors(cpu_percent)

            # Update label (must be called from main thread)
            self.monitor_label.configure(text=display_text, text_color=fg_color)
            self.configure(fg_color=bg_color)

            # Store current metrics for tooltip
            self.current_cpu = cpu_percent
            self.current_ram_used = ram_used_gb
            self.current_ram_total = ram_total_gb

        except Exception as e:
            print(f"Error updating display: {e}")

    def _get_colors(self, cpu_percent: float) -> tuple:
        """
        Get background and foreground colors based on CPU usage.

        User's thresholds:
        - 0-74%: Green
        - 75-84%: Yellow
        - 85-90%: Orange
        - 90%+: Red
        - 100%: Red with emphasis

        Args:
            cpu_percent: Current CPU usage percentage

        Returns:
            tuple: (bg_color, fg_color)
        """
        if cpu_percent < 75:
            # Green: healthy
            return ("#1a3a1a", "#90EE90")  # Dark green bg, light green text
        elif cpu_percent < 85:
            # Yellow: elevated
            return ("#3a3a1a", "#FFEB3B")  # Dark yellow bg, bright yellow text
        elif cpu_percent < 90:
            # Orange: high
            return ("#3a2a1a", "#FFA500")  # Dark orange bg, bright orange text
        else:
            # Red: critical (90%+)
            return ("#3a1a1a", "#FF4444")  # Dark red bg, bright red text

    def _on_enter(self, event):
        """Handle mouse enter - schedule tooltip display."""
        self.show_timer = self.after(500, self._show_tooltip)

    def _on_leave(self, event):
        """Handle mouse leave - hide tooltip."""
        if self.show_timer:
            self.after_cancel(self.show_timer)
            self.show_timer = None
        self._hide_tooltip()

    def _show_tooltip(self):
        """Show detailed system information tooltip."""
        try:
            if self.tooltip_window:
                return

            # Get CPU frequency
            try:
                cpu_freq = psutil.cpu_freq()
                freq_text = f"Base: {cpu_freq.current:.1f} GHz"
                if cpu_freq.max:
                    freq_text += f" | Max: {cpu_freq.max:.1f} GHz"
            except Exception:
                freq_text = "Frequency: Unknown"

            # Build tooltip text
            tooltip_text = (
                f"{self.cpu_model}\n"
                f"{self.physical_cores} physical cores, {self.logical_cores} logical threads\n"
                f"{freq_text}\n"
                f"\n"
                f"Current CPU: {self.current_cpu:.1f}%\n"
                f"Current RAM: {self.current_ram_used:.1f} / {self.current_ram_total:.1f} GB"
            )

            # Create tooltip window
            self.tooltip_window = ctk.CTkToplevel(self.winfo_toplevel())
            self.tooltip_window.wm_overrideredirect(True)
            self.tooltip_window.wm_attributes("-topmost", True)
            self.tooltip_window.wm_attributes("-toolwindow", True)

            label = ctk.CTkLabel(
                self.tooltip_window,
                text=tooltip_text,
                bg_color=("#333333", "#333333"),
                text_color=("white", "white"),
                corner_radius=5,
                wraplength=250,
                font=ctk.CTkFont(size=9)
            )
            label.pack(padx=8, pady=8)

            # Position tooltip
            self.tooltip_window.update_idletasks()
            tooltip_width = self.tooltip_window.winfo_width()
            tooltip_height = self.tooltip_window.winfo_height()

            # Get monitor position
            monitor_x = self.monitor_label.winfo_rootx()
            monitor_y = self.monitor_label.winfo_rooty()
            monitor_width = self.monitor_label.winfo_width()
            monitor_height = self.monitor_label.winfo_height()

            # Position to the right, vertically centered
            x = monitor_x + monitor_width + 10
            y = monitor_y + (monitor_height // 2) - (tooltip_height // 2)

            # Ensure tooltip stays on screen
            screen_width = self.winfo_screenwidth()
            if x + tooltip_width > screen_width:
                x = monitor_x - tooltip_width - 10

            self.tooltip_window.wm_geometry(f"+{x}+{y}")
            self.tooltip_window.lift()

        except Exception as e:
            print(f"Tooltip error: {e}")

    def _hide_tooltip(self):
        """Hide the tooltip."""
        if self.tooltip_window:
            try:
                self.tooltip_window.destroy()
            except Exception:
                pass
            self.tooltip_window = None
