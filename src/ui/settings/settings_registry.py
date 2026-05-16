"""
Settings Registry for CasePrepd.

Provides a declarative way to define application settings with metadata
for automatic UI generation. Adding a new setting requires only a single
SettingsRegistry.register() call - no UI code changes needed.

Architecture:
- SettingDefinition: Dataclass with all metadata for one setting
- SettingsRegistry: Class-level registry that organizes settings by category
- _register_all_settings(): Called on import to register all app settings
  (delegates to per-tab modules in src/ui/settings/registry/)

Example - Adding a new setting:
    SettingsRegistry.register(SettingDefinition(
        key="my_new_setting",
        label="My New Feature",
        category="General",  # Creates tab if needed
        setting_type=SettingType.CHECKBOX,
        tooltip="Description of what this does.",
        default=False,
        getter=lambda: prefs.get("my_new_setting", False),
        setter=lambda v: prefs.set("my_new_setting", v),
    ))
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class SettingType(Enum):
    """
    Types of settings with corresponding UI widgets.

    Each type maps to a widget class in settings_widgets.py:
    - SLIDER: SliderSetting (numeric range)
    - CHECKBOX: CheckboxSetting (boolean)
    - DROPDOWN: DropdownSetting (selection)
    - SPINBOX: SpinboxSetting (integer +/-)
    - PATH: Reserved for future file/folder picker
    - BUTTON: ActionButton (executes action on click)
    - CUSTOM: CustomWidgetSetting (custom widget factory)
    """

    SLIDER = "slider"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    PATH = "path"
    SPINBOX = "spinbox"
    BUTTON = "button"
    CUSTOM = "custom"  # For complex widgets like question list


@dataclass
class SettingDefinition:
    """
    Complete metadata for a single application setting.

    The SettingsDialog reads these definitions and auto-generates
    appropriate widgets, tooltips, and save/load behavior.

    Attributes:
        key: Unique identifier (used for storage in preferences)
        label: Display name shown in the UI
        category: Tab name in settings dialog (groups related settings)
        setting_type: Widget type to render
        tooltip: Explanation shown on hover. Can be a string or callable
            returning a string (for dynamic content evaluated at display time).
        default: Default value when no preference is saved
        min_value: Minimum value (for SLIDER, SPINBOX)
        max_value: Maximum value (for SLIDER, SPINBOX)
        step: Increment between values (for SLIDER)
        options: List of (display_text, value) tuples (for DROPDOWN).
            Can also be a callable returning such a list (for dynamic options
            evaluated when the dialog opens, not at registration time).
        getter: Function that returns the current value
        setter: Function that applies a new value
        action: Function to execute on click (for BUTTON)
        widget_factory: Function(parent) -> widget (for CUSTOM type)
    """

    key: str
    label: str
    category: str
    setting_type: SettingType
    tooltip: str | Callable[[], str]
    default: Any
    min_value: float = None
    max_value: float = None
    step: float = 1
    options: list | Callable[[], list] = field(default_factory=list)
    getter: Callable[[], Any] = None
    setter: Callable[[Any], None] = None
    action: Callable[[], None] = None
    widget_factory: Callable = None
    section: str | None = None  # Sub-group within a category (for collapsible sections)


class SettingsRegistry:
    """
    Global registry of all application settings.

    Settings are organized by category for tabbed display. The dialog
    reads from this registry to generate its UI dynamically.

    Usage:
        # Register a setting
        SettingsRegistry.register(my_setting_definition)

        # Get all categories (for tabs)
        categories = SettingsRegistry.get_categories()

        # Get settings in a category
        settings = SettingsRegistry.get_settings_for_category("Performance")
    """

    _settings: ClassVar[dict[str, SettingDefinition]] = {}
    _categories: ClassVar[dict[str, list[str]]] = {}  # category -> [setting_keys]
    _category_order: ClassVar[list[str]] = []  # Preserve registration order

    @classmethod
    def register(cls, setting: SettingDefinition) -> None:
        """
        Register a setting definition.

        Args:
            setting: SettingDefinition with all metadata.
        """
        cls._settings[setting.key] = setting

        if setting.category not in cls._categories:
            cls._categories[setting.category] = []
            cls._category_order.append(setting.category)

        if setting.key not in cls._categories[setting.category]:
            cls._categories[setting.category].append(setting.key)

    @classmethod
    def get_categories(cls) -> list[str]:
        """Get all category names in registration order."""
        return cls._category_order.copy()

    @classmethod
    def get_settings_for_category(cls, category: str) -> list[SettingDefinition]:
        """Get all settings in a category."""
        keys = cls._categories.get(category, [])
        return [cls._settings[k] for k in keys]

    @classmethod
    def get_all_settings(cls) -> list[SettingDefinition]:
        """Get all registered settings."""
        return list(cls._settings.values())

    @classmethod
    def get_setting(cls, key: str) -> SettingDefinition | None:
        """Get a specific setting by key."""
        return cls._settings.get(key)

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (for testing)."""
        cls._settings.clear()
        cls._categories.clear()
        cls._category_order.clear()


def _apply_font_delta(widget, delta: int) -> None:
    """
    Recursively adjust font sizes on all widgets by delta points.

    Walks the widget tree and updates any widget that has a font
    configuration. Safe to call on any widget type — silently
    skips widgets without font support.
    """
    try:
        font = widget.cget("font")
        if isinstance(font, tuple) and len(font) >= 2:
            new_size = max(8, font[1] + delta)
            new_font = (font[0], new_size) + tuple(font[2:])
            widget.configure(font=new_font)
    except Exception:
        pass
    try:
        for child in widget.winfo_children():
            _apply_font_delta(child, delta)
    except Exception:
        pass


def _register_all_settings():
    """
    Register all CasePrepd settings.

    Called on module import. Delegates to per-tab registration modules
    in src/ui/settings/registry/. Tab order follows registration order
    of the first setting in each category — see each module for content.
    """
    from src.ui.settings.registry import advanced as advanced_processing
    from src.ui.settings.registry import (
        appearance,
        corpus,
        export,
        logging_tab,
        preprocessing,
        search,
    )
    from src.ui.settings.registry import vocabulary as vocab_tab
    from src.user_preferences import get_user_preferences

    prefs = get_user_preferences()

    appearance.register(prefs)
    vocab_tab.register(prefs)
    preprocessing.register(prefs)
    corpus.register(prefs)
    search.register(prefs)
    export.register(prefs)
    logging_tab.register(prefs)
    # Advanced "Processing" section — defined here so the Advanced tab
    # appears AFTER Logging in the original tab order.
    advanced_processing.register(prefs)
    # The semantic_export_relevance_floor setting belongs to the Export
    # tab but was historically registered last; keep that behavior so
    # in-tab setting order is preserved exactly.
    export.register_relevance_floor(prefs)


# Register all settings when this module is imported
_register_all_settings()

# Register Advanced tab settings (must be after base registration)
from .advanced_registry import _register_advanced_settings  # noqa: E402

_register_advanced_settings()
