"""
Advanced tab Processing section (parallel processing limit).

Note: the rest of the Advanced tab settings are registered by
advanced_registry.py from config_defaults; this module only adds
the Processing section that originally lived in settings_registry.
"""

from src.ui.settings.settings_registry import (
    SettingDefinition,
    SettingsRegistry,
    SettingType,
)


def register(prefs) -> None:
    """Register the Advanced tab Processing section setting."""
    SettingsRegistry.register(
        SettingDefinition(
            key="resource_usage_pct",
            label="Parallel processing limit",
            category="Advanced",
            section="Processing",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "How many parallel workers to allow during processing, expressed "
                "as a percentage of your CPU cores.\n\n"
                "Example: On an 8-core machine at 75%, up to 6 workers can run "
                "simultaneously. RAM is also checked — each worker needs "
                "~2GB, so low-RAM systems will be capped regardless.\n\n"
                "Affects:\n"
                "• Vocabulary extraction: Up to 4 algorithms run in parallel\n"
                "• Search indexing: Embedding and FAISS index creation\n"
                "• Search: Up to 4 queries answered simultaneously\n\n"
                "Lower values keep your computer responsive during processing. "
                "Higher values finish faster but may cause slowdowns."
            ),
            default=75,
            min_value=25,
            max_value=100,
            step=5,
            getter=lambda: prefs.get("resource_usage_pct", 75),
            setter=lambda v: prefs.set("resource_usage_pct", int(v)),
        )
    )
