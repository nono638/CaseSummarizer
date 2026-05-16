"""
Search tab settings (retrieval weights, default questions).
"""

from src.ui.settings.settings_registry import (
    SettingDefinition,
    SettingsRegistry,
    SettingType,
)


def _create_default_questions_widget(parent):
    """Factory function to create the DefaultQuestionsWidget."""
    from src.ui.settings.questions_widget import DefaultQuestionsWidget

    return DefaultQuestionsWidget(parent)


def _save_default_questions(questions_data: list[dict]) -> None:
    """Persist buffered questions list to the manager (single disk write)."""
    if questions_data is None:
        return
    from src.services import SemanticService

    manager = SemanticService().get_default_questions_manager()
    manager.replace_all(questions_data)


def register(prefs) -> None:
    """Register the Search tab settings."""
    SettingsRegistry.register(
        SettingDefinition(
            key="retrieval_weight_faiss",
            label="Semantic search weight (FAISS)",
            category="Search",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Weight for semantic (FAISS) search when retrieving document context "
                "for search results.\n\n"
                "Semantic search understands meaning and concepts. Phrasing is "
                "forgiving — asking 'Who are the parties?' can find passages about "
                "'plaintiff and defendant' even without those exact words.\n\n"
                "Higher values give semantic results more influence when both "
                "algorithms find the same passage."
            ),
            default=1.0,
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            getter=lambda: prefs.get("retrieval_weight_faiss", 1.0),
            setter=lambda v: prefs.set("retrieval_weight_faiss", float(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="retrieval_weight_bm25",
            label="Exact match weight (BM25+)",
            category="Search",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Weight for exact-match (BM25+) search when retrieving document "
                "context for search results.\n\n"
                "BM25+ favors exact text matches — it finds passages containing "
                "the precise words in your question. Best for specific legal terms, "
                "names, and dates.\n\n"
                "Higher values give exact-match results more influence when both "
                "algorithms find the same passage."
            ),
            default=0.8,
            min_value=0.0,
            max_value=2.0,
            step=0.1,
            getter=lambda: prefs.get("retrieval_weight_bm25", 0.8),
            setter=lambda v: prefs.set("retrieval_weight_bm25", float(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="semantic_default_questions",
            label="Default Searches",
            category="Search",
            setting_type=SettingType.CUSTOM,
            tooltip=(
                "Manage the searches that are automatically run after document "
                "processing. Enable/disable individual searches using checkboxes. "
                "Add new searches or edit existing ones."
            ),
            default=None,
            setter=_save_default_questions,
            widget_factory=_create_default_questions_widget,
        )
    )
