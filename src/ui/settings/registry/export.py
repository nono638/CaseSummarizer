"""
Export tab settings (auto-open, search relevance floor).
"""

from src.ui.settings.settings_registry import (
    SettingDefinition,
    SettingsRegistry,
    SettingType,
)


def register(prefs) -> None:
    """Register the Export tab settings."""
    SettingsRegistry.register(
        SettingDefinition(
            key="auto_open_exports",
            label="Auto-open exported files",
            category="Export",
            setting_type=SettingType.CHECKBOX,
            tooltip=(
                "When enabled, exported files (TXT, PDF, HTML) are "
                "automatically opened in their default application after export.\n\n"
                "Disable this if you export many files at once or prefer to "
                "manually open files."
            ),
            default=True,
            getter=lambda: prefs.get("auto_open_exports", True),
            setter=lambda v: prefs.set("auto_open_exports", v),
        )
    )


def register_relevance_floor(prefs) -> None:
    """Register the search relevance floor setting.

    Registered separately so it can be appended after the Advanced tab
    settings while remaining inside the Export category — preserves
    the original tab order (Export before Advanced).
    """
    from src.config import SEMANTIC_EXPORT_RELEVANCE_FLOOR

    SettingsRegistry.register(
        SettingDefinition(
            key="semantic_export_relevance_floor",
            label="Search relevance floor",
            category="Export",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Minimum relevance score (0-1) for a search result to be\n"
                "included in exports. Results below this threshold are\n"
                "excluded — they're usually not relevant enough to be useful.\n\n"
                "Default: 0.51 (51%)"
            ),
            default=SEMANTIC_EXPORT_RELEVANCE_FLOOR,
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            getter=lambda: prefs.get(
                "semantic_export_relevance_floor", SEMANTIC_EXPORT_RELEVANCE_FLOOR
            ),
            setter=lambda v: prefs.set("semantic_export_relevance_floor", float(v)),
        )
    )
