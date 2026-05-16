"""
Appearance tab settings (theme, font size, UI scale).
"""

from src.ui.settings.settings_registry import (
    SettingDefinition,
    SettingsRegistry,
    SettingType,
    _apply_font_delta,
)


def _apply_appearance_mode(prefs, mode: str) -> None:
    """Apply appearance mode change and refresh styles."""
    import customtkinter as ctk

    prefs.set("appearance_mode", mode)
    ctk.set_appearance_mode(mode)

    from src.ui.styles import reinitialize_styles

    reinitialize_styles()


def _apply_font_change(prefs, offset) -> None:
    """Apply font size change immediately to all widgets."""
    import tkinter as tk

    old_offset = int(prefs.get("font_size_offset", 0) or 0)
    prefs.set("font_size_offset", offset)
    new_offset = int(offset)

    from src.ui.theme import scale_fonts

    scale_fonts(new_offset)

    from src.ui.styles import reinitialize_styles

    reinitialize_styles(font_offset=new_offset)

    delta = new_offset - old_offset
    root = tk._default_root
    if root and delta != 0:
        _apply_font_delta(root, delta)
        root.event_generate("<<FontChanged>>")


def register(prefs) -> None:
    """Register the Appearance tab settings."""
    SettingsRegistry.register(
        SettingDefinition(
            key="appearance_mode",
            label="Theme",
            category="Appearance",
            setting_type=SettingType.DROPDOWN,
            tooltip=(
                "Choose the application color theme.\n\n"
                "• Dark: Dark backgrounds with light text (default)\n"
                "• Light: Light backgrounds with dark text\n"
                "• System: Follow your Windows theme setting\n\n"
                "Takes effect immediately."
            ),
            default="Dark",
            options=[
                ("Dark", "Dark"),
                ("Light", "Light"),
                ("System", "System"),
            ],
            getter=lambda: prefs.get("appearance_mode", "Dark"),
            setter=lambda v: _apply_appearance_mode(prefs, v),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="font_size_offset",
            label="Font Size Adjustment",
            category="Appearance",
            setting_type=SettingType.SPINBOX,
            tooltip=(
                "Adjust the font size used throughout the application,\n"
                "including table rows (vocabulary, search, documents).\n\n"
                "Enter a point offset (positive = larger, negative = smaller).\n"
                "Examples: +4 for high-DPI screens, -2 for compact layout."
            ),
            default=0,
            min_value=-4,
            max_value=10,
            getter=lambda: prefs.get("font_size_offset", 0),
            setter=lambda v: _apply_font_change(prefs, v),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="ui_scale_pct",
            label="UI Scale (%)",
            category="Appearance",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Scale all widget dimensions (buttons, tables, dialogs).\n\n"
                "Does NOT affect font sizes (use Font Size Adjustment for that).\n"
                "Useful for 4K monitors where widgets appear cramped.\n\n"
                "• 75%: Compact layout\n"
                "• 100%: Default\n"
                "• 125-150%: Recommended for 4K monitors\n"
                "• 200%: Maximum\n\n"
                "Requires restart to take effect."
            ),
            default=100,
            min_value=75,
            max_value=200,
            step=25,
            getter=lambda: prefs.get("ui_scale_pct", 100),
            setter=lambda v: prefs.set("ui_scale_pct", int(v)),
        )
    )
