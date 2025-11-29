"""
LocalScribe - Custom Dialogs (CustomTkinter Refactor)
"""
import time

import customtkinter as ctk


class ModelLoadProgressDialog(ctk.CTkToplevel):
    """
    Progress dialog for model loading, refactored for CustomTkinter.
    """
    def __init__(self, model_name, parent=None):
        super().__init__(parent)
        self.model_name = model_name
        self.start_time = time.time()

        self.title("Loading Model")
        self.geometry("400x200")
        self.grab_set()  # Make modal

        self.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(self, text=f"Loading {self.model_name} Model", font=ctk.CTkFont(size=14, weight="bold"))
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        info_label = ctk.CTkLabel(self, text="This may take 30-60 seconds depending on your hardware.", wraplength=350)
        info_label.grid(row=1, column=0, padx=20, pady=5)

        self.progress_bar = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress_bar.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.progress_bar.start()

        self.timer_label = ctk.CTkLabel(self, text="Elapsed time: 0.0 seconds")
        self.timer_label.grid(row=3, column=0, padx=20, pady=5)

        self.status_label = ctk.CTkLabel(self, text="Initializing...")
        self.status_label.grid(row=4, column=0, padx=20, pady=5)

        self._update_timer()

    def _update_timer(self):
        """Update the elapsed time display."""
        elapsed = time.time() - self.start_time
        self.timer_label.configure(text=f"Elapsed time: {elapsed:.1f} seconds")
        self.after(100, self._update_timer) # Schedule next update

    def finish_success(self):
        """Mark loading as complete and close dialog."""
        self.progress_bar.stop()
        self.progress_bar.set(1)
        self.status_label.configure(text="Model loaded successfully!", text_color="green")
        self.after(1000, self.destroy) # Auto-close after 1s

class SimpleProgressDialog(ctk.CTkToplevel):
    """
    Simple progress dialog, refactored for CustomTkinter.
    """
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x150")
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        self.message_label = ctk.CTkLabel(self, text="Starting...", wraplength=350)
        self.message_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.progress_bar = ctk.CTkProgressBar(self, mode="determinate")
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

    def update_progress(self, percentage, message):
        """Update progress display."""
        self.progress_bar.set(percentage / 100.0)
        self.message_label.configure(text=message)
        self.update_idletasks() # Force UI update


class SettingsDialog(ctk.CTkToplevel):
    """
    Settings dialog for LocalScribe configuration.
    Handles CPU fraction selection for parallel document processing.
    """

    def __init__(self, parent=None, current_cpu_fraction=0.5, on_save_callback=None):
        """
        Initialize the Settings dialog.

        Args:
            parent: Parent window
            current_cpu_fraction: Current CPU fraction setting (0.25, 0.5, or 0.75)
            on_save_callback: Callback function called with new cpu_fraction when user saves
        """
        super().__init__(parent)
        self.title("Settings")
        self.geometry("500x300")
        self.grab_set()  # Make modal
        self.resizable(False, False)

        self.current_cpu_fraction = current_cpu_fraction
        self.on_save_callback = on_save_callback
        self.result = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)

        # Title
        title_label = ctk.CTkLabel(
            self,
            text="Application Settings",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Content frame
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        content_frame.grid_columnconfigure(0, weight=1)

        # CPU Fraction Setting
        cpu_label = ctk.CTkLabel(
            content_frame,
            text="Parallel Processing - CPU Allocation:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        cpu_label.grid(row=0, column=0, sticky="w", pady=(0, 5))

        cpu_info = ctk.CTkLabel(
            content_frame,
            text="Choose how many CPU cores LocalScribe can use for parallel document processing.\n"
                 "Lower values = less system impact. Higher values = faster processing.\n"
                 "Default: 1/2 cores (balanced).",
            text_color="gray",
            wraplength=400,
            justify="left"
        )
        cpu_info.grid(row=1, column=0, sticky="w", pady=(0, 15))

        # Radio button options
        self.cpu_var = ctk.StringVar(
            value=str(current_cpu_fraction)
        )

        options = [
            ("🟢 Low Impact (1/4 cores) - Minimal system impact, slower processing", "0.25"),
            ("🟡 Balanced (1/2 cores) - Recommended for most machines", "0.5"),
            ("🔴 Aggressive (3/4 cores) - Maximum speed, higher system impact", "0.75"),
        ]

        for idx, (label, value) in enumerate(options):
            radio = ctk.CTkRadioButton(
                content_frame,
                text=label,
                variable=self.cpu_var,
                value=value,
                font=ctk.CTkFont(size=11)
            )
            radio.grid(row=2 + idx, column=0, sticky="w", pady=5)

        # Button frame
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))
        button_frame.grid_columnconfigure(0, weight=1)

        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self.cancel,
            width=100
        )
        cancel_btn.grid(row=0, column=0, sticky="e", padx=(0, 10))

        save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            command=self.save,
            width=100
        )
        save_btn.grid(row=0, column=1, sticky="e")

    def save(self):
        """Save settings and close dialog."""
        self.result = float(self.cpu_var.get())
        if self.on_save_callback:
            self.on_save_callback(self.result)
        self.destroy()

    def cancel(self):
        """Close dialog without saving."""
        self.result = None
        self.destroy()
