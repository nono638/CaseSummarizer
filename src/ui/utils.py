"""
LocalScribe - UI Utility Functions
"""
import customtkinter as ctk

def create_tooltip(widget, text, position="right"):
    """
    Create a stable tooltip that appears on hover without flickering.
    Uses delayed display and proper positioning to prevent enter/leave loops.

    Args:
        widget: The widget to attach the tooltip to
        text: The tooltip text to display
        position: "right" (default) or "left" - which side of the widget the tooltip appears
    """
    tooltip_window = None
    show_timer = None

    def schedule_show():
        """Schedule tooltip to appear after delay (prevents flickering)."""
        nonlocal show_timer
        cancel_show()  # Cancel any existing scheduled show
        show_timer = widget.after(500, show_tooltip_delayed)  # 500ms delay

    def cancel_show():
        """Cancel scheduled tooltip display."""
        nonlocal show_timer
        if show_timer:
            widget.after_cancel(show_timer)
            show_timer = None

    def show_tooltip_delayed():
        """Display tooltip (called after delay)."""
        nonlocal tooltip_window, show_timer
        show_timer = None

        if tooltip_window:
            return

        widget.update_idletasks()
        tooltip_window = ctk.CTkToplevel(widget.winfo_toplevel())
        tooltip_window.wm_overrideredirect(True)
        tooltip_window.wm_attributes("-topmost", True)
        tooltip_window.wm_attributes("-toolwindow", True)

        label = ctk.CTkLabel(tooltip_window, text=text,
                             bg_color=("#333333", "#333333"),
                             text_color=("white", "white"),
                             corner_radius=5,
                             wraplength=200)
        label.pack(padx=5, pady=5)

        tooltip_window.update_idletasks()
        tooltip_width = tooltip_window.winfo_width()
        tooltip_height = tooltip_window.winfo_height()

        widget_x = widget.winfo_rootx()
        widget_y = widget.winfo_rooty()
        widget_width = widget.winfo_width()
        widget_height = widget.winfo_height()

        screen_width = widget.winfo_screenwidth()
        screen_height = widget.winfo_screenheight()

        if position == "left":
            x = widget_x - tooltip_width - 15
        else:
            x = widget_x + widget_width + 15

        if x + tooltip_width > screen_width:
            x = widget_x - tooltip_width - 15

        if x < 0:
            x = max(0, min(widget_x, screen_width - tooltip_width - 10))

        y = widget_y + (widget_height // 2) - (tooltip_height // 2)
        y = max(0, min(y, screen_height - tooltip_height))

        tooltip_window.wm_geometry(f"+{x}+{y}")
        tooltip_window.lift()
        tooltip_window.update_idletasks()

    def hide_tooltip(event):
        """Hide tooltip immediately (no delay)."""
        nonlocal tooltip_window
        cancel_show()
        if tooltip_window:
            try:
                tooltip_window.destroy()
            except:
                pass
            tooltip_window = None

    def on_enter(event):
        schedule_show()

    def on_leave(event):
        hide_tooltip(event)

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)
