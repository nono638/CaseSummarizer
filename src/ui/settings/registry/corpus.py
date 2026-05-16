"""
Corpus tab settings (corpus management widget).
"""

from src.ui.settings.settings_registry import (
    SettingDefinition,
    SettingsRegistry,
    SettingType,
)


def _create_corpus_settings_widget(parent):
    """Factory function to create the CorpusSettingsWidget."""
    from src.ui.settings.corpus_widget import CorpusSettingsWidget

    return CorpusSettingsWidget(parent)


def register(prefs) -> None:
    """Register the Corpus tab settings."""
    SettingsRegistry.register(
        SettingDefinition(
            key="corpus_management",
            label="Corpus Management",
            category="Corpus",
            setting_type=SettingType.CUSTOM,
            tooltip=(
                "Manage your corpus of past transcripts for BM25 vocabulary extraction. "
                "The corpus helps identify case-specific terminology by comparing against "
                "your typical work."
            ),
            default=None,
            widget_factory=_create_corpus_settings_widget,
        )
    )
