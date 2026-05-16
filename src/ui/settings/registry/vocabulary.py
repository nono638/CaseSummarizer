"""
Vocabulary tab settings: sort method, filters, model reset/import, indicator patterns.
"""

import logging
import os

from src.ui.settings.settings_registry import (
    SettingDefinition,
    SettingsRegistry,
    SettingType,
)

logger = logging.getLogger(__name__)


def _create_corpus_warning_widget(parent):
    """Factory for corpus status warning banner with dynamic refresh."""
    import customtkinter as ctk

    from src.services import VocabularyService
    from src.ui.theme import COLORS

    # Start collapsed — CTkFrame defaults to 200px height, which would create
    # dead space when no warning is needed (corpus has 5+ docs).
    frame = ctk.CTkFrame(parent, fg_color="transparent", height=1)
    frame._warning_frame = None
    frame._warning_label = None
    frame.pack_propagate(False)  # stay at height=1 until a warning is shown

    def update_warning():
        """Update the warning banner based on current corpus status."""
        corpus_manager = VocabularyService().get_corpus_manager()
        doc_count = corpus_manager.get_document_count()

        if doc_count < 5:
            warning_text = (
                f"Corpus not ready ({doc_count}/5 documents). "
                "ML predictions are less accurate without a corpus of past transcripts. "
                "Add documents in Settings > Corpus."
            )

            if frame._warning_frame is None:
                frame._warning_frame = ctk.CTkFrame(
                    frame, fg_color=COLORS["warning_banner_bg"], corner_radius=6
                )
                frame._warning_frame.pack(fill="x", pady=(0, 10), padx=5)
                frame._warning_label = ctk.CTkLabel(
                    frame._warning_frame,
                    text=warning_text,
                    text_color=COLORS["warning_banner_fg"],
                    wraplength=400,
                    justify="left",
                    anchor="w",
                )
                frame._warning_label.pack(anchor="w", padx=10, pady=8)
            else:
                frame._warning_label.configure(text=warning_text)
                if not frame._warning_frame.winfo_ismapped():
                    frame._warning_frame.pack(fill="x", pady=(0, 10), padx=5)
            frame.pack_propagate(True)  # expand to fit the warning banner
        else:
            if frame._warning_frame is not None and frame._warning_frame.winfo_ismapped():
                frame._warning_frame.pack_forget()
            frame.pack_propagate(False)  # collapse back to 1px
            frame.configure(height=1)

    update_warning()
    frame.bind("<Map>", lambda e: update_warning())

    return frame


def _create_column_visibility_widget(parent):
    """Factory function to create the ColumnVisibilityWidget."""
    from src.ui.settings.columns_widget import ColumnVisibilityWidget

    return ColumnVisibilityWidget(parent)


def _save_column_visibility(prefs, visibility: dict) -> None:
    """Persist column visibility dict to preferences."""
    if visibility is not None:
        prefs.set("vocab_column_visibility", visibility)


def _open_corpus_folder(corpus_dir) -> None:
    """Open the corpus folder in the system file explorer."""
    # UI-003: Verify CORPUS_DIR exists before trying to open
    if not corpus_dir.exists():
        corpus_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Windows
        os.startfile(str(corpus_dir))
    except AttributeError:
        # macOS/Linux fallback
        import subprocess
        import sys

        try:
            if sys.platform == "darwin":
                subprocess.run(["open", str(corpus_dir)])
            else:
                subprocess.run(["xdg-open", str(corpus_dir)])
        except Exception as e:
            logger.warning("Could not open corpus folder: %s", e)


def _reset_vocab_model() -> None:
    """Reset vocabulary ML model to default (keep feedback history)."""
    from tkinter import messagebox

    result = messagebox.askyesno(
        "Reset Vocabulary Model",
        "Reset the vocabulary ranking model to default settings?\n\n"
        "This will undo any personalization from your thumbs up/down "
        "feedback, but your feedback history will be preserved.\n\n"
        "You can retrain the model later using your existing feedback.",
        icon="warning",
    )

    if result:
        from src.services import VocabularyService

        learner = VocabularyService().get_meta_learner()
        if learner.reset_to_default():
            messagebox.showinfo(
                "Reset Complete",
                "Vocabulary model has been reset to default.\n\n"
                "Your feedback history is preserved. The model will "
                "retrain when you provide more feedback.",
            )
        else:
            messagebox.showerror(
                "Reset Failed",
                "Failed to reset vocabulary model. Check the log file for details.",
            )


def _reset_vocab_model_and_history() -> None:
    """Reset vocabulary ML model AND clear all feedback history."""
    from tkinter import messagebox

    result = messagebox.askyesno(
        "Reset Model and Clear History",
        "⚠️ CAUTION: This will:\n\n"
        "• Reset the vocabulary ranking model to default\n"
        "• DELETE all your thumbs up/down feedback history\n\n"
        "This action cannot be undone. Are you sure?",
        icon="warning",
    )

    if result:
        # Double-check for destructive action
        confirm = messagebox.askyesno(
            "Confirm Complete Reset",
            "Are you absolutely sure?\n\nAll feedback you've given will be permanently deleted.",
            icon="warning",
        )

        if confirm:
            from src.services import VocabularyService

            vocab_svc = VocabularyService()
            learner = vocab_svc.get_meta_learner()
            feedback_manager = vocab_svc.get_feedback_manager()

            model_ok = learner.reset_to_default()
            feedback_ok = feedback_manager.clear_all_feedback()

            if model_ok and feedback_ok:
                messagebox.showinfo(
                    "Reset Complete",
                    "Vocabulary model and feedback history have been reset.\n\n"
                    "The system is now using default settings.",
                )
            else:
                messagebox.showerror(
                    "Reset Partially Failed",
                    f"Model reset: {'OK' if model_ok else 'FAILED'}\n"
                    f"Feedback clear: {'OK' if feedback_ok else 'FAILED'}\n\n"
                    "Check the log file for details.",
                )


def _export_vocab_model() -> None:
    """Export user vocabulary model from settings."""
    from tkinter import filedialog, messagebox

    from src.services.model_io_service import export_user_model

    dest = filedialog.asksaveasfilename(
        title="Export Vocabulary Model",
        defaultextension=".pkl",
        filetypes=[("Pickle files", "*.pkl")],
        initialfile="vocab_model.pkl",
    )
    if not dest:
        return
    from pathlib import Path

    ok, msg = export_user_model(Path(dest))
    if ok:
        messagebox.showinfo("Export Complete", msg)
    else:
        messagebox.showerror("Export Failed", msg)


def _import_vocab_model() -> None:
    """Import vocabulary model from settings."""
    from tkinter import filedialog, messagebox

    messagebox.showwarning(
        "Security Warning",
        "Only load model files from sources you trust.\n"
        "Model files can contain executable code.\n\n"
        "Press OK to continue.",
    )

    src = filedialog.askopenfilename(
        title="Import Vocabulary Model",
        filetypes=[("Pickle files", "*.pkl")],
    )
    if not src:
        return
    from pathlib import Path

    from src.services.model_io_service import import_user_model

    ok, msg = import_user_model(Path(src))
    if ok:
        messagebox.showinfo("Import Complete", msg)
    else:
        messagebox.showerror("Import Failed", msg)


def _export_vocab_feedback() -> None:
    """Export user feedback history from settings."""
    from tkinter import filedialog, messagebox

    from src.services import VocabularyService
    from src.services.model_io_service import export_user_feedback

    feedback_mgr = VocabularyService().get_feedback_manager()
    dest = filedialog.asksaveasfilename(
        title="Export Feedback History",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv")],
        initialfile="feedback_history.csv",
    )
    if not dest:
        return
    from pathlib import Path

    ok, msg = export_user_feedback(Path(dest), feedback_mgr)
    if ok:
        messagebox.showinfo("Export Complete", msg)
    else:
        messagebox.showerror("Export Failed", msg)


def _import_vocab_feedback() -> None:
    """Import feedback history from settings."""
    from tkinter import filedialog, messagebox

    src = filedialog.askopenfilename(
        title="Import Feedback History",
        filetypes=[("CSV files", "*.csv")],
    )
    if not src:
        return

    result = messagebox.askyesnocancel(
        "Import Mode",
        "How should the imported feedback be combined?\n\n"
        "Yes = Replace (old data backed up)\n"
        "No = Append to existing\n"
        "Cancel = Abort",
    )
    if result is None:
        return
    mode = "replace" if result else "append"

    from pathlib import Path

    from src.services import VocabularyService
    from src.services.model_io_service import import_user_feedback

    feedback_mgr = VocabularyService().get_feedback_manager()
    ok, msg, count = import_user_feedback(Path(src), mode, feedback_mgr)

    if not ok:
        messagebox.showerror("Import Failed", msg)
        return

    retrain = messagebox.askyesno(
        "Retrain Model?",
        f"{msg}\n\nRetrain the vocabulary model with the new feedback?",
    )
    if retrain:
        learner = VocabularyService().get_meta_learner()
        learner.train()
        messagebox.showinfo("Import Complete", f"Imported {count} records. Model retrained.")
    else:
        messagebox.showinfo("Import Complete", msg)


def _get_indicator_patterns(p):
    """Get current indicator pattern config with shipped defaults."""
    from src.config import (
        DEFAULT_NEGATIVE_INDICATORS,
        DEFAULT_NEGATIVE_REGEX_OVERRIDE,
        DEFAULT_POSITIVE_INDICATORS,
        DEFAULT_POSITIVE_REGEX_OVERRIDE,
    )

    return {
        "positive_strings": p.get("vocab_positive_indicators", DEFAULT_POSITIVE_INDICATORS),
        "negative_strings": p.get("vocab_negative_indicators", DEFAULT_NEGATIVE_INDICATORS),
        "positive_override": p.get(
            "vocab_positive_regex_override", DEFAULT_POSITIVE_REGEX_OVERRIDE
        ),
        "negative_override": p.get(
            "vocab_negative_regex_override", DEFAULT_NEGATIVE_REGEX_OVERRIDE
        ),
    }


def _create_indicator_pattern_widget(parent):
    """Factory function to create the IndicatorPatternWidget."""
    from src.ui.settings.indicator_pattern_widget import IndicatorPatternWidget

    return IndicatorPatternWidget(parent)


def _save_indicator_patterns(prefs, value: dict) -> None:
    """Save indicator patterns to preferences and trigger retrain."""
    if not isinstance(value, dict):
        return
    prefs.set("vocab_positive_indicators", value.get("positive_strings", []))
    prefs.set("vocab_negative_indicators", value.get("negative_strings", []))
    prefs.set("vocab_positive_regex_override", value.get("positive_override", ""))
    prefs.set("vocab_negative_regex_override", value.get("negative_override", ""))

    # Trigger preference learner retrain with new features
    # (indicator_patterns cache auto-invalidates when preferences change)
    try:
        from src.services import VocabularyService

        learner = VocabularyService().get_meta_learner()
        if learner.train():
            logger.info("Vocabulary model retrained with updated indicator patterns")
        else:
            logger.debug("Vocabulary model retrain skipped (insufficient data)")
    except Exception as e:
        logger.warning("Could not retrain vocabulary model: %s", e)


def register(prefs) -> None:
    """Register the Vocabulary tab settings."""
    from src.config import BM25_ENABLED, CORPUS_DIR, VOCABULARY_SORT_METHOD

    _register_top_section(prefs)
    _register_sort_and_filters(prefs)
    _register_corpus_buttons(prefs, BM25_ENABLED, CORPUS_DIR)
    _register_model_buttons(prefs)
    _register_thresholds(prefs, VOCABULARY_SORT_METHOD)
    _register_indicator_patterns(prefs)


def _register_top_section(prefs) -> None:
    """Register the corpus warning banner."""
    SettingsRegistry.register(
        SettingDefinition(
            key="corpus_status_warning",
            label="",  # No label for banner
            category="Vocabulary",
            setting_type=SettingType.CUSTOM,
            tooltip="",
            default=None,
            widget_factory=_create_corpus_warning_widget,
        )
    )


def _register_sort_and_filters(prefs) -> None:
    """Register vocab sort, title page, CSV format, and column visibility settings."""
    from src.config import VOCABULARY_SORT_METHOD

    SettingsRegistry.register(
        SettingDefinition(
            key="vocab_sort_method",
            label="Sort vocabulary by",
            category="Vocabulary",
            setting_type=SettingType.DROPDOWN,
            tooltip=(
                "Controls how vocabulary terms are sorted in the results table.\n\n"
                "• Quality Score: Terms the ML model predicts you'll approve appear first. "
                "This improves as you rate more terms.\n\n"
                "• Rarity: Unusual/rare words appear first (based on Google Books corpus)."
            ),
            options=[
                ("Quality Score", "quality_score"),
                ("Rarity", "rarity"),
            ],
            default="quality_score" if VOCABULARY_SORT_METHOD == "quality_score" else "rarity",
            getter=lambda: prefs.get("vocab_sort_method", VOCABULARY_SORT_METHOD),
            setter=lambda v: prefs.set("vocab_sort_method", v),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="title_page_handling",
            label="Title page handling",
            category="Vocabulary",
            setting_type=SettingType.DROPDOWN,
            tooltip=(
                "Controls how title/cover pages are handled during processing.\n\n"
                "• Use for vocabulary only: Title pages are included when extracting "
                "vocabulary (good source of canonical party and attorney names) but "
                "excluded from search and key excerpts (where they cause false positives).\n\n"
                "• Include in all processing: Title pages are never removed.\n\n"
                "• Exclude from all processing: Title pages are removed before vocabulary "
                "extraction and before search/key excerpts.\n\n"
                "Changes apply on next document load."
            ),
            default="vocab_only",
            options=[
                ("Use title pages for vocabulary only", "vocab_only"),
                ("Include title pages in all processing", "include_all"),
                ("Exclude title pages from all processing", "exclude_all"),
            ],
            getter=lambda: prefs.get("title_page_handling", "vocab_only"),
            setter=lambda v: prefs.set("title_page_handling", v),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="vocab_export_format",
            label="CSV export columns",
            category="Vocabulary",
            setting_type=SettingType.DROPDOWN,
            tooltip=(
                "Controls which columns are included when saving vocabulary to CSV. "
                "'All columns' includes Quality Score, Frequency, and Rank for "
                "Excel filtering. 'Basic' exports Term, Type, and Role. "
                "'Terms only' exports just the vocabulary terms."
            ),
            default="basic",
            options=[
                ("All columns (with quality metrics)", "all"),
                ("Basic (Term, Type, Role)", "basic"),
                ("Terms only", "terms_only"),
            ],
            getter=lambda: prefs.get("vocab_export_format", "basic"),
            setter=lambda v: prefs.set("vocab_export_format", v),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="vocab_column_visibility",
            label="",  # Widget has its own header
            category="Vocabulary",
            setting_type=SettingType.CUSTOM,
            tooltip="",  # Widget has its own tooltip
            default=None,
            getter=lambda: prefs.get("vocab_column_visibility", {}),
            setter=lambda v: _save_column_visibility(prefs, v),
            widget_factory=_create_column_visibility_widget,
        )
    )


def _register_corpus_buttons(prefs, BM25_ENABLED, CORPUS_DIR) -> None:
    """Register BM25 toggle and Open Corpus Folder button."""
    SettingsRegistry.register(
        SettingDefinition(
            key="bm25_enabled",
            label="Enable Corpus Analysis (BM25)",
            category="Vocabulary",
            setting_type=SettingType.CHECKBOX,
            tooltip=(
                "Compare your current document against your library of past "
                "transcripts to identify case-specific terminology. Terms that "
                "are frequent in this document but rare in your corpus are likely "
                "important. Requires 5+ documents in your corpus folder.\n\n"
                "🔒 Privacy: All analysis happens locally on your computer - "
                "no documents or data are ever sent to external servers."
            ),
            default=BM25_ENABLED,
            getter=lambda: prefs.get("bm25_enabled", BM25_ENABLED),
            setter=lambda v: prefs.set("bm25_enabled", v),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="open_corpus_folder",
            label="Open Corpus Folder",
            category="Vocabulary",
            setting_type=SettingType.BUTTON,
            tooltip=(
                "Add your past transcripts (PDF, TXT, RTF) to this folder to "
                "build your personal vocabulary baseline. The more documents "
                "you add, the better the system identifies unusual terms "
                "specific to each new case.\n\n"
                "📁 Location: " + str(CORPUS_DIR)
            ),
            default=None,
            action=lambda: _open_corpus_folder(CORPUS_DIR),
        )
    )


def _register_model_buttons(prefs) -> None:
    """Register the model reset/export/import buttons."""
    SettingsRegistry.register(
        SettingDefinition(
            key="reset_vocab_model",
            label="Reset Vocabulary Model",
            category="Vocabulary",
            setting_type=SettingType.BUTTON,
            tooltip=(
                "Reset the vocabulary ranking model to its default (shipped) state. "
                "This undoes any personalization from your thumbs up/down feedback, "
                "but keeps your feedback history so you can retrain later.\n\n"
                "Use this if the model seems to be ranking terms poorly after "
                "you've given it feedback."
            ),
            default=None,
            action=_reset_vocab_model,
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="reset_vocab_model_and_history",
            label="Reset Model and Clear History",
            category="Vocabulary",
            setting_type=SettingType.BUTTON,
            tooltip=(
                "⚠️ COMPLETE RESET: Resets the vocabulary model AND deletes all "
                "your thumbs up/down feedback history. This cannot be undone.\n\n"
                "Use this for a complete fresh start if you want to begin "
                "personalizing from scratch."
            ),
            default=None,
            action=_reset_vocab_model_and_history,
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="export_vocab_model",
            label="Export Model",
            category="Vocabulary",
            setting_type=SettingType.BUTTON,
            tooltip="Export your personalized vocabulary model to a file for backup or transfer.",
            default=None,
            action=_export_vocab_model,
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="import_vocab_model",
            label="Import Model",
            category="Vocabulary",
            setting_type=SettingType.BUTTON,
            tooltip="Import a vocabulary model from a file. The current model will be backed up.",
            default=None,
            action=_import_vocab_model,
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="export_vocab_feedback",
            label="Export Feedback History",
            category="Vocabulary",
            setting_type=SettingType.BUTTON,
            tooltip="Export your feedback history (thumbs up/down ratings) to a CSV file.",
            default=None,
            action=_export_vocab_feedback,
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="import_vocab_feedback",
            label="Import Feedback History",
            category="Vocabulary",
            setting_type=SettingType.BUTTON,
            tooltip="Import feedback history from a CSV file. Choose to replace or append.",
            default=None,
            action=_import_vocab_feedback,
        )
    )


def _register_thresholds(prefs, VOCABULARY_SORT_METHOD) -> None:
    """Register vocabulary filtering threshold sliders/spinboxes."""
    SettingsRegistry.register(
        SettingDefinition(
            key="single_word_rarity_threshold",
            label="Single-word filtering threshold",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Filter single words in the top X% of English vocabulary. "
                "Lower = more aggressive filtering, Higher = keep more words.\n\n"
                "Example: 0.50 filters the most common 50% of English words."
            ),
            default=0.50,
            min_value=0.10,
            max_value=0.90,
            step=0.05,
            getter=lambda: prefs.get("single_word_rarity_threshold", 0.50),
            setter=lambda v: prefs.set("single_word_rarity_threshold", float(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="phrase_rarity_threshold",
            label="Phrase filtering threshold",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Filter multi-word phrases where all words are in the top X% of English. "
                "Lower = more aggressive filtering, Higher = keep more phrases.\n\n"
                "Example: 0.50 filters phrases where every word is in the top 50%."
            ),
            default=0.50,
            min_value=0.10,
            max_value=0.90,
            step=0.05,
            getter=lambda: prefs.get("phrase_rarity_threshold", 0.50),
            setter=lambda v: prefs.set("phrase_rarity_threshold", float(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="vocab_min_occurrences",
            label="Minimum term occurrences",
            category="Vocabulary",
            setting_type=SettingType.SPINBOX,
            tooltip=(
                "Filter terms appearing fewer than N times in your documents.\n\n"
                "Higher values filter more aggressively, removing OCR errors and "
                "one-off terms. Value of 1 keeps all terms.\n\n"
                "Note: Person names are exempt from this filter."
            ),
            default=2,
            min_value=1,
            max_value=5,
            getter=lambda: prefs.get("vocab_min_occurrences", 2),
            setter=lambda v: prefs.set("vocab_min_occurrences", int(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="vocab_occurrence_exception_score",
            label="Occurrence floor exception score",
            category="Vocabulary",
            setting_type=SettingType.SPINBOX,
            tooltip=(
                "A term that falls below the occurrence floor will still appear if its "
                "quality score meets or exceeds this threshold.\n\n"
                "Set to 100 to disable exceptions entirely. Lower values allow more "
                "low-occurrence terms to slip through based on score alone.\n\n"
                "Default 97 means only near-perfect-scoring terms bypass the floor."
            ),
            default=97,
            min_value=50,
            max_value=100,
            getter=lambda: prefs.get("vocab_occurrence_exception_score", 97),
            setter=lambda v: prefs.set("vocab_occurrence_exception_score", int(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="vocab_score_floor",
            label="Minimum quality score",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Filter terms with quality scores below this threshold.\n\n"
                "Higher values show only high-relevance results. "
                "Lower values include more terms but may include noise.\n\n"
                "The quality score is based on ML predictions of term usefulness."
            ),
            default=55,
            min_value=45,
            max_value=85,
            step=5,
            getter=lambda: prefs.get("vocab_score_floor", 55),
            setter=lambda v: prefs.set("vocab_score_floor", int(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="vocab_filtered_score_floor",
            label="Filtered list minimum score",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Hide filtered-out terms with scores below this threshold.\n\n"
                "Terms in the lower 'Filtered out' section scoring below this "
                "value are hidden entirely — they're usually noise (common words, "
                "nonsense phrases).\n\n"
                "Default: 40. Range: 20–49."
            ),
            default=40,
            min_value=20,
            max_value=49,
            step=1,
            getter=lambda: prefs.get("vocab_filtered_score_floor", 40),
            setter=lambda v: prefs.set("vocab_filtered_score_floor", int(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="phrase_mean_rarity_threshold",
            label="Phrase mean commonality",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Filter phrases where the AVERAGE word commonality exceeds this "
                "threshold. Lower values = more aggressive filtering.\n\n"
                "Example: 0.40 filters phrases where the average word is in the "
                "top 40% of common English words.\n\n"
                "Works alongside 'Phrase filtering threshold' which checks the "
                "RAREST word in the phrase."
            ),
            default=0.40,
            min_value=0.10,
            max_value=0.90,
            step=0.05,
            getter=lambda: prefs.get("phrase_mean_rarity_threshold", 0.40),
            setter=lambda v: prefs.set("phrase_mean_rarity_threshold", float(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="non_ner_single_passthrough_threshold",
            label="RAKE/BM25 single-word passthrough",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Allow single words found by RAKE/BM25 to pass through rarity "
                "filtering if their rarity score meets this threshold. "
                "Higher = stricter (fewer passthroughs).\n\n"
                "Words not in the dictionary are treated as rare (score = "
                "'Rarity score for unknown words' setting below)."
            ),
            default=0.80,
            min_value=0.50,
            max_value=0.95,
            step=0.05,
            getter=lambda: prefs.get("non_ner_single_passthrough_threshold", 0.80),
            setter=lambda v: prefs.set("non_ner_single_passthrough_threshold", float(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="non_ner_phrase_max_passthrough_threshold",
            label="RAKE/BM25 phrase passthrough (rarest word)",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Allow multi-word RAKE/BM25 phrases to pass through rarity "
                "filtering if the rarest word's score meets this threshold. "
                "Both this AND the average threshold below must be met.\n\n"
                "Higher = stricter (fewer phrase passthroughs)."
            ),
            default=0.85,
            min_value=0.50,
            max_value=0.95,
            step=0.05,
            getter=lambda: prefs.get("non_ner_phrase_max_passthrough_threshold", 0.85),
            setter=lambda v: prefs.set("non_ner_phrase_max_passthrough_threshold", float(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="non_ner_phrase_mean_passthrough_threshold",
            label="RAKE/BM25 phrase passthrough (adjusted mean)",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Allow multi-word RAKE/BM25 phrases to pass through rarity "
                "filtering if the adjusted mean word rarity meets this threshold. "
                "Both this AND the rarest-word threshold above must be met.\n\n"
                "The adjusted mean excludes common filler words (controlled by "
                "the 'common word floor' setting below).\n\n"
                "Higher = stricter (fewer phrase passthroughs)."
            ),
            default=0.65,
            min_value=0.30,
            max_value=0.80,
            step=0.05,
            getter=lambda: prefs.get("non_ner_phrase_mean_passthrough_threshold", 0.65),
            setter=lambda v: prefs.set("non_ner_phrase_mean_passthrough_threshold", float(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="non_ner_phrase_common_word_floor",
            label="Adjusted mean: common word floor",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Words with rarity score below this floor are excluded from "
                "the adjusted mean rarity calculation. This prevents common "
                "filler words (like 'of', 'the', 'and') from dragging down "
                "the mean rarity of phrases that contain rare words.\n\n"
                "Example: 0.10 excludes the top 10% most common English words."
            ),
            default=0.10,
            min_value=0.05,
            max_value=0.30,
            step=0.05,
            getter=lambda: prefs.get("non_ner_phrase_common_word_floor", 0.10),
            setter=lambda v: prefs.set("non_ner_phrase_common_word_floor", float(v)),
        )
    )

    SettingsRegistry.register(
        SettingDefinition(
            key="non_ner_unknown_word_rarity",
            label="Rarity score for unknown words",
            category="Vocabulary",
            setting_type=SettingType.SLIDER,
            tooltip=(
                "Rarity score assigned to words not found in the Google frequency "
                "dataset. Higher values treat unknown words as rarer, making them "
                "more likely to be rescued.\n\n"
                "Unknown words are often proper nouns or specialized terms."
            ),
            default=0.85,
            min_value=0.50,
            max_value=1.00,
            step=0.05,
            getter=lambda: prefs.get("non_ner_unknown_word_rarity", 0.85),
            setter=lambda v: prefs.set("non_ner_unknown_word_rarity", float(v)),
        )
    )


def _register_indicator_patterns(prefs) -> None:
    """Register the indicator pattern custom widget."""
    SettingsRegistry.register(
        SettingDefinition(
            key="vocab_indicator_patterns",
            label="Indicator Patterns",
            category="Vocabulary",
            setting_type=SettingType.CUSTOM,
            tooltip=(
                "Define strings that indicate good or bad vocabulary terms.\n\n"
                "Positive indicators: Strings found in terms you tend to keep "
                "(e.g., 'dr.', 'plaintiff').\n\n"
                "Negative indicators: Strings found in terms you tend to skip "
                "(e.g., 'direct', 'redirect', 'cross').\n\n"
                "These become ML features — the model learns from your votes "
                "whether these patterns correlate with terms you keep or skip."
            ),
            default=None,
            getter=lambda: _get_indicator_patterns(prefs),
            setter=lambda v: _save_indicator_patterns(prefs, v),
            widget_factory=_create_indicator_pattern_widget,
        )
    )
