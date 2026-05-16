"""
Text Preprocessing tab settings.
"""

from src.ui.settings.settings_registry import (
    SettingDefinition,
    SettingsRegistry,
    SettingType,
)

_PREPROCESS_TOGGLES = [
    (
        "preprocess_index_pages",
        "Remove index pages",
        "Remove index/concordance pages from the end of transcripts.\n\n"
        "These are alphabetical reference pages that list where topics "
        "appear — useful in print but noise for search and vocabulary extraction.",
    ),
    (
        "preprocess_headers_footers",
        "Remove headers/footers",
        "Remove repetitive headers and footers that appear on every page.\n\n"
        "Detected by frequency analysis — text that repeats on most pages "
        "is identified as a header or footer and removed.",
    ),
    (
        "preprocess_line_numbers",
        "Remove line numbers",
        "Remove margin line numbers (1-25) common in court transcripts.\n\n"
        "These numbers are used for reference during depositions but add "
        "noise when processing text for AI analysis.",
    ),
    (
        "preprocess_page_boundaries",
        "Clean page boundary artifacts",
        "Clean artifacts caused by collapsed page boundaries in PDF extraction.\n\n"
        "When PDF text extraction doesn't preserve page breaks, line numbers, "
        "page numbers, reporter initials, and headers can merge into body text. "
        "This cleaner detects and removes those artifacts.\n\n"
        "Example: '...this 1 2 3 ... 24 sn Proceedings 29 1 Court.' becomes "
        "'...this Court.'",
    ),
    (
        "preprocess_transcript_artifacts",
        "Clean transcript artifacts",
        "Remove transcript-specific artifacts like standalone page numbers "
        "and inline concordance citations.\n\n"
        "Handles patterns like embedded page:line references that appear "
        "in some transcript formats.",
    ),
]


def _create_custom_patterns_widget(parent):
    """Factory function to create the CustomPatternsWidget."""
    from src.ui.settings.patterns_widget import CustomPatternsWidget

    return CustomPatternsWidget(
        parent,
        tooltip_text=(
            "Add custom text patterns to remove from documents.\n\n"
            "These are matched case-insensitively and removed if they "
            "appear 3 or more times (indicating they're repeated "
            "headers or footers).\n\n"
            "Examples:\n"
            "• Firm names: 'SMITH & JONES LLP'\n"
            "• Reporter info: 'JANE DOE, CSR'\n"
            "• Custom headers: 'CONFIDENTIAL - DO NOT DISTRIBUTE'"
        ),
    )


def _save_custom_patterns(prefs, value: str) -> None:
    """Save custom patterns to preferences."""
    if value is not None:
        prefs.set("custom_header_footer_patterns", value)


def register(prefs) -> None:
    """Register the Text Preprocessing tab settings."""
    for _key, _label, _tooltip in _PREPROCESS_TOGGLES:
        SettingsRegistry.register(
            SettingDefinition(
                key=_key,
                label=_label,
                category="Text Preprocessing",
                setting_type=SettingType.CHECKBOX,
                tooltip=_tooltip + "\n\nChanges apply on next document load.",
                default=True,
                getter=(lambda k=_key: prefs.get(k, True)),
                setter=(lambda v, k=_key: prefs.set(k, v)),
            )
        )

    SettingsRegistry.register(
        SettingDefinition(
            key="custom_header_footer_patterns",
            label="Custom Header/Footer Patterns",
            category="Text Preprocessing",
            setting_type=SettingType.CUSTOM,
            tooltip="Add custom patterns to remove from document headers and footers.",
            default="",
            setter=lambda v: _save_custom_patterns(prefs, v),
            widget_factory=_create_custom_patterns_widget,
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="header_footer_short_line_detection",
            label="Aggressive short-line detection",
            category="Text Preprocessing",
            setting_type=SettingType.CHECKBOX,
            tooltip=(
                "When enabled, short lines (under 70 characters) containing words "
                "like 'plaintiff', 'defendant', 'direct', or 'cross' are treated "
                "as headers if they repeat 3+ times.\n\n"
                "This catches section headers like 'PLAINTIFF / MR. SMITH' that "
                "might otherwise be missed.\n\n"
                "Disable if legitimate short lines are being incorrectly removed."
            ),
            default=True,
            getter=lambda: prefs.get("header_footer_short_line_detection", True),
            setter=lambda v: prefs.set("header_footer_short_line_detection", v),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="header_footer_min_occurrences",
            label="Minimum occurrences for removal",
            category="Text Preprocessing",
            setting_type=SettingType.SPINBOX,
            tooltip=(
                "How many times a line must appear to be considered a header/footer.\n\n"
                "Lower values (2-3) are more aggressive and catch headers that "
                "don't appear on every page.\n\n"
                "Higher values (4-5) are more conservative and only remove "
                "content that appears very frequently.\n\n"
                "Default: 3"
            ),
            default=3,
            min_value=2,
            max_value=10,
            getter=lambda: prefs.get("header_footer_min_occurrences", 3),
            setter=lambda v: prefs.set("header_footer_min_occurrences", int(v)),
        )
    )
