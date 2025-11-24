"""
Tooltip Helper for CustomTkinter Widgets

Provides stable tooltips that appear on hover without flickering.
Uses delayed display (500ms) and intelligent positioning fallbacks.
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

        # If tooltip already exists, don't create another
        if tooltip_window:
            return

        # Force widget geometry update before querying position
        widget.update_idletasks()

        # Create tooltip window using toplevel parent for proper hierarchy
        tooltip_window = ctk.CTkToplevel(widget.winfo_toplevel())
        tooltip_window.wm_overrideredirect(True)  # Remove window decorations
        tooltip_window.wm_attributes("-topmost", True)  # Keep on top
        tooltip_window.wm_attributes("-toolwindow", True)  # Prevent taskbar appearance on Windows

        label = ctk.CTkLabel(tooltip_window, text=text,
                             bg_color=("#333333", "#333333"),  # Dark background
                             text_color=("white", "white"),  # White text
                             corner_radius=5,
                             wraplength=200)  # Wrap text after 200 pixels
        label.pack(padx=5, pady=5)

        # Force tooltip to calculate its size (use update_idletasks for reliable sizing)
        tooltip_window.update_idletasks()
        tooltip_width = tooltip_window.winfo_width()
        tooltip_height = tooltip_window.winfo_height()

        # Get widget position on screen (after widget geometry is finalized)
        widget_x = widget.winfo_rootx()
        widget_y = widget.winfo_rooty()
        widget_width = widget.winfo_width()
        widget_height = widget.winfo_height()

        # Get screen dimensions
        screen_width = widget.winfo_screenwidth()
        screen_height = widget.winfo_screenheight()

        # Position tooltip with cascading fallback logic
        if position == "left":
            # Try left side first
            x = widget_x - tooltip_width - 15
        else:  # position == "right" (default)
            # Try right side first
            x = widget_x + widget_width + 15

        # Check boundaries and apply cascading fallback
        if x + tooltip_width > screen_width:
            # Right position would go off-screen, try left
            x = widget_x - tooltip_width - 15
            if x < 0:
                # Left also off-screen, center on widget
                x = widget_x + (widget_width // 2) - (tooltip_width // 2)

        # Constrain to screen boundaries
        x = max(0, min(x, screen_width - tooltip_width))

        # Vertical positioning (centered with widget, but constrained to screen)
        y = widget_y + (widget_height // 2) - (tooltip_height // 2)
        y = max(0, min(y, screen_height - tooltip_height))

        # Set position and show
        tooltip_window.wm_geometry(f"+{int(x)}+{int(y)}")

    def hide_tooltip(event):
        """Hide tooltip immediately."""
        nonlocal tooltip_window
        cancel_show()
        if tooltip_window:
            try:
                tooltip_window.destroy()
            except Exception:
                pass
            tooltip_window = None

    def on_enter(event):
        """Handle mouse enter on widget."""
        schedule_show()

    def on_leave(event):
        """Handle mouse leave from widget."""
        hide_tooltip(event)

    # Bind events
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)
