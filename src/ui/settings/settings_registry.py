"""
Settings Registry for LocalScribe.

Provides a declarative way to define application settings with metadata
for automatic UI generation. Adding a new setting requires only a single
SettingsRegistry.register() call - no UI code changes needed.

Architecture:
- SettingDefinition: Dataclass with all metadata for one setting
- SettingsRegistry: Class-level registry that organizes settings by category
- _register_all_settings(): Called on import to register all app settings

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

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class SettingType(Enum):
    """
    Types of settings with corresponding UI widgets.

    Each type maps to a widget class in settings_widgets.py:
    - SLIDER: SliderSetting (numeric range)
    - CHECKBOX: CheckboxSetting (boolean)
    - DROPDOWN: DropdownSetting (selection)
    - SPINBOX: SpinboxSetting (integer +/-)
    - PATH: Reserved for future file/folder picker
    """
    SLIDER = "slider"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    PATH = "path"
    SPINBOX = "spinbox"


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
        tooltip: Explanation shown on hover (helps users understand the setting)
        default: Default value when no preference is saved
        min_value: Minimum value (for SLIDER, SPINBOX)
        max_value: Maximum value (for SLIDER, SPINBOX)
        step: Increment between values (for SLIDER)
        options: List of (display_text, value) tuples (for DROPDOWN)
        getter: Function that returns the current value
        setter: Function that applies a new value
    """
    key: str
    label: str
    category: str
    setting_type: SettingType
    tooltip: str
    default: Any
    min_value: float = None
    max_value: float = None
    step: float = 1
    options: list = field(default_factory=list)
    getter: Callable[[], Any] = None
    setter: Callable[[Any], None] = None


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

    _settings: dict[str, SettingDefinition] = {}
    _categories: dict[str, list[str]] = {}  # category -> [setting_keys]
    _category_order: list[str] = []  # Preserve registration order

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


def _register_all_settings():
    """
    Register all LocalScribe settings.

    This function is called on module import. To add a new setting,
    add a SettingsRegistry.register() call here.

    Settings are grouped by category (tab):
    - Performance: Parallel processing, CPU allocation
    - Summarization: AI summary settings
    - Vocabulary: Term extraction settings
    """
    # Import lazily to avoid circular imports
    from src.user_preferences import get_user_preferences
    from src.config import (
        USER_DEFINED_MAX_WORKER_COUNT,
        VOCABULARY_DISPLAY_LIMIT,
        VOCABULARY_DISPLAY_MAX,
        VOCABULARY_SORT_BY_RARITY,
        DEFAULT_SUMMARY_WORDS,
        MIN_SUMMARY_WORDS,
        MAX_SUMMARY_WORDS,
    )

    prefs = get_user_preferences()

    # ===================================================================
    # PERFORMANCE TAB
    # ===================================================================

    SettingsRegistry.register(SettingDefinition(
        key="parallel_workers_auto",
        label="Auto-detect CPU cores",
        category="Performance",
        setting_type=SettingType.CHECKBOX,
        tooltip=(
            "When enabled, LocalScribe automatically detects the optimal "
            "number of parallel workers based on your CPU. Disable this "
            "to manually set the worker count below."
        ),
        default=True,
        getter=lambda: not prefs.get("user_picks_max_workers", False),
        setter=lambda v: prefs.set("user_picks_max_workers", not v),
    ))

    SettingsRegistry.register(SettingDefinition(
        key="parallel_workers_count",
        label="Manual worker count",
        category="Performance",
        setting_type=SettingType.SPINBOX,
        tooltip=(
            "Number of parallel workers when auto-detect is disabled. "
            "Higher values process documents faster but use more RAM. "
            "Range: 1-8. Recommended: 2 for most systems, 4 for 16GB+ RAM."
        ),
        default=USER_DEFINED_MAX_WORKER_COUNT,
        min_value=1,
        max_value=8,
        getter=lambda: prefs.get("user_defined_max_workers", 2),
        setter=lambda v: prefs.set("user_defined_max_workers", v),
    ))

    SettingsRegistry.register(SettingDefinition(
        key="cpu_fraction",
        label="CPU allocation",
        category="Performance",
        setting_type=SettingType.DROPDOWN,
        tooltip=(
            "Fraction of CPU cores to use for document processing. "
            "Lower values reduce system impact. Higher values process "
            "faster but may slow other applications."
        ),
        default=0.5,
        options=[
            ("1/4 cores (Low impact)", 0.25),
            ("1/2 cores (Balanced)", 0.5),
            ("3/4 cores (Maximum speed)", 0.75),
        ],
        getter=prefs.get_cpu_fraction,
        setter=prefs.set_cpu_fraction,
    ))

    # ===================================================================
    # SUMMARIZATION TAB
    # ===================================================================

    SettingsRegistry.register(SettingDefinition(
        key="default_summary_words",
        label="Default summary length (words)",
        category="Summarization",
        setting_type=SettingType.SLIDER,
        tooltip=(
            "Target word count for AI-generated summaries. The actual "
            "length may vary slightly. Longer summaries capture more "
            "detail but take more time to generate."
        ),
        default=DEFAULT_SUMMARY_WORDS,
        min_value=MIN_SUMMARY_WORDS,
        max_value=MAX_SUMMARY_WORDS,
        step=50,
        getter=lambda: prefs.get("summary_words", DEFAULT_SUMMARY_WORDS),
        setter=lambda v: prefs.set("summary_words", int(v)),
    ))

    # ===================================================================
    # VOCABULARY TAB
    # ===================================================================

    SettingsRegistry.register(SettingDefinition(
        key="vocab_display_limit",
        label="Vocabulary display limit",
        category="Vocabulary",
        setting_type=SettingType.SLIDER,
        tooltip=(
            f"Maximum terms shown in the vocabulary table. Higher values "
            f"may slow the GUI on large documents. Range: 10-{VOCABULARY_DISPLAY_MAX}. "
            f"The full vocabulary is always saved to CSV."
        ),
        default=VOCABULARY_DISPLAY_LIMIT,
        min_value=10,
        max_value=VOCABULARY_DISPLAY_MAX,
        step=10,
        getter=lambda: prefs.get("vocab_display_limit", VOCABULARY_DISPLAY_LIMIT),
        setter=lambda v: prefs.set("vocab_display_limit", int(v)),
    ))

    SettingsRegistry.register(SettingDefinition(
        key="vocab_sort_by_rarity",
        label="Sort vocabulary by rarity",
        category="Vocabulary",
        setting_type=SettingType.CHECKBOX,
        tooltip=(
            "When enabled, vocabulary lists show the rarest (most unusual) "
            "terms first. Disable for alphabetical order. Rarity is based "
            "on word frequency in the Google Books corpus."
        ),
        default=VOCABULARY_SORT_BY_RARITY,
        getter=lambda: prefs.get("vocab_sort_by_rarity", VOCABULARY_SORT_BY_RARITY),
        setter=lambda v: prefs.set("vocab_sort_by_rarity", v),
    ))


# Register all settings when this module is imported
_register_all_settings()
