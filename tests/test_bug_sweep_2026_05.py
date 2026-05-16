"""
Regression tests for bug sweep fixes (May 2026).

Each test fails without the corresponding fix. Grouped by category to mirror
the auto-fix list in the bug sweep briefing.
"""

import importlib
import inspect

import pytest

# ---------------------------------------------------------------------------
# A. Dead code deletions
# ---------------------------------------------------------------------------


class TestDeadCodeRemoved:
    """Confirm that deleted symbols / modules cannot be re-imported."""

    def test_coreference_resolver_module_gone(self):
        """src.core.preprocessing.coreference_resolver must no longer import."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("src.core.preprocessing.coreference_resolver")

    def test_coreference_resolver_not_in_preprocessing_all(self):
        """CoreferenceResolver symbol must not be re-exported."""
        mod = importlib.import_module("src.core.preprocessing")
        assert "CoreferenceResolver" not in getattr(mod, "__all__", [])
        assert not hasattr(mod, "CoreferenceResolver")

    def test_pipeline_indicator_module_gone(self):
        """src.ui.pipeline_indicator must no longer import."""
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("src.ui.pipeline_indicator")

    def test_filter_sentences_removed(self):
        """_filter_sentences must be removed from key_sentences module."""
        mod = importlib.import_module("src.core.summarization.key_sentences")
        assert not hasattr(mod, "_filter_sentences")

    def test_dead_config_constants_removed(self):
        """LOG_FILE, RESIZE_DEBOUNCE_MS, etc. must be gone from src.config."""
        cfg = importlib.import_module("src.config")
        for name in (
            "LOG_FILE",
            "LOG_FORMAT",
            "LOG_DATE_FORMAT",
            "DEBUG_DEFAULT_FILE",
            "RESIZE_DEBOUNCE_MS",
            "ERROR_DISPLAY_MAX_CHARS",
            "CHUNK_OVERLAP_FRACTION",
            "VOCAB_FEEDBACK_CSV",
            "SPACY_THREAD_TIMEOUT_SEC",
            "MODEL_CONFIGS",
            "MODEL_CONFIG_FILE",
            "load_model_configs",
        ):
            assert not hasattr(cfg, name), f"{name} should be removed from src.config"


# ---------------------------------------------------------------------------
# B. Dead parameter removal
# ---------------------------------------------------------------------------


class TestAnswerModeRemoved:
    """answer_mode parameter should be gone end-to-end."""

    def test_semantic_worker_no_answer_mode(self):
        """SemanticWorker.__init__ must not accept answer_mode."""
        from src.services.semantic_worker import SemanticWorker

        sig = inspect.signature(SemanticWorker.__init__)
        assert "answer_mode" not in sig.parameters

    def test_semantic_orchestrator_no_answer_mode(self):
        """SemanticOrchestrator.__init__ must not accept answer_mode."""
        from src.core.semantic.semantic_orchestrator import SemanticOrchestrator

        sig = inspect.signature(SemanticOrchestrator.__init__)
        assert "answer_mode" not in sig.parameters


class TestIncludeVerificationRemoved:
    """include_verification(_colors) parameters must be gone from exporters."""

    def test_export_semantic_results_no_param(self):
        """semantic_exporter.export_semantic_results must not accept include_verification_colors."""
        from src.core.export.semantic_exporter import export_semantic_results

        sig = inspect.signature(export_semantic_results)
        assert "include_verification_colors" not in sig.parameters

    def test_export_semantic_html_no_param(self):
        """html_builder.export_semantic_html must not accept include_verification."""
        from src.core.export.html_builder import export_semantic_html

        sig = inspect.signature(export_semantic_html)
        assert "include_verification" not in sig.parameters

    def test_export_combined_no_param(self):
        """combined_exporter.export_combined must not accept include_verification."""
        from src.core.export.combined_exporter import export_combined

        sig = inspect.signature(export_combined)
        assert "include_verification" not in sig.parameters

    def test_build_combined_html_no_param(self):
        """combined_html_builder.build_combined_html must not accept include_verification."""
        from src.core.export.combined_html_builder import build_combined_html

        sig = inspect.signature(build_combined_html)
        assert "include_verification" not in sig.parameters

    def test_export_service_methods_no_param(self):
        """ExportService combined/semantic methods must not accept include_verification."""
        from src.services.export_service import ExportService

        for name in (
            "export_semantic_to_word",
            "export_semantic_to_pdf",
            "export_semantic_to_html",
            "export_combined_html",
            "export_combined_to_word",
            "export_combined_to_pdf",
        ):
            method = getattr(ExportService, name)
            sig = inspect.signature(method)
            assert "include_verification" not in sig.parameters, (
                f"ExportService.{name} still has include_verification"
            )


# ---------------------------------------------------------------------------
# C. Dependency hygiene
# ---------------------------------------------------------------------------


class TestRequirements:
    """requirements files must list direct dependencies the code imports."""

    def test_runtime_requirements_lists_torch_and_transformers(self):
        """requirements.txt must declare torch and transformers."""
        from pathlib import Path

        text = Path("requirements.txt").read_text(encoding="utf-8").lower()
        assert "torch" in text
        assert "transformers" in text

    def test_dev_requirements_lists_pandas_and_pyinstaller(self):
        """requirements-dev.txt must declare pandas and pyinstaller."""
        from pathlib import Path

        text = Path("requirements-dev.txt").read_text(encoding="utf-8").lower()
        assert "pandas" in text
        assert "pyinstaller" in text


# ---------------------------------------------------------------------------
# D. Silent failure fixed
# ---------------------------------------------------------------------------


def test_transcript_cleaner_logs_regex_error_at_warning(caplog, monkeypatch):
    """Invalid regex in transcript patterns must log at WARNING, not DEBUG."""
    import logging

    from src.core.preprocessing import transcript_cleaner as tc

    bad_config = {
        "inline_citation_patterns": [
            {
                "name": "broken_pattern",
                "pattern": "[unterminated",
                "replacement": "",
                "enabled": True,
            }
        ]
    }
    monkeypatch.setattr(tc, "_load_transcript_patterns", lambda: bad_config)

    cleaner = tc.TranscriptCleaner()
    with caplog.at_level(logging.WARNING, logger=tc.__name__):
        cleaner._strip_inline_citations("hello world")

    matched = [
        r
        for r in caplog.records
        if r.levelno >= logging.WARNING and "broken_pattern" in r.getMessage()
    ]
    assert matched, "Expected WARNING-level log for invalid regex in transcript pattern"


# ---------------------------------------------------------------------------
# E. UI behavior fixes
# ---------------------------------------------------------------------------


class TestOnStopClickedCancelsTimers:
    """_on_stop_clicked must cancel pending retry timers and disable the button."""

    def test_source_cancels_retry_ids(self):
        """Source of _on_stop_clicked must reference both retry IDs and after_cancel."""
        from src.ui.main_window import MainWindow

        source = inspect.getsource(MainWindow._on_stop_clicked)
        assert "_extraction_retry_id" in source
        assert "_preprocessing_retry_id" in source
        assert "after_cancel" in source

    def test_source_disables_stop_button(self):
        """Source must disable stop_btn before showing the confirmation modal."""
        from src.ui.main_window import MainWindow

        source = inspect.getsource(MainWindow._on_stop_clicked)
        assert 'stop_btn.configure(state="disabled")' in source


class TestPreprocessingProgressGuard:
    """progress messages must be accepted during the preprocessing phase."""

    def test_guard_checks_all_phases(self):
        """_handle_queue_message must check preprocessing and semantic flags too."""
        from src.ui.main_window import MainWindow

        source = inspect.getsource(MainWindow._handle_queue_message)
        # Look for any guard mentioning all three flags
        assert "_preprocessing_active" in source
        assert "_semantic_answering_active" in source


class TestDragDropUsesTkSplitlist:
    """drag-drop handler must use tk.splitlist instead of hand-rolled parser."""

    def test_uses_tk_splitlist(self):
        """Look up the drop handler and confirm it calls self.tk.splitlist."""
        import re
        from pathlib import Path

        text = Path("src/ui/main_window.py").read_text(encoding="utf-8")
        assert re.search(r"self\.tk\.splitlist\(raw_data\)", text)


# ---------------------------------------------------------------------------
# F. CLI alignment
# ---------------------------------------------------------------------------


class TestCliWriteJson:
    """write_json must gate vocabulary.json on data presence and write search.json
    whenever a query was run (independent of --only)."""

    def test_search_json_written_when_query_supplied(self, tmp_path):
        """search.json must be written for any non-None search_result."""
        from types import SimpleNamespace

        from src.cli import write_json

        search = SimpleNamespace(
            question="q",
            citation="c",
            source_summary="s",
            relevance=0.5,
        )
        # only={"vocab"} — but search_result is present
        write_json(tmp_path, [], [], search, {"vocab"})
        assert (tmp_path / "search.json").exists()

    def test_vocabulary_json_skipped_when_vocab_empty(self, tmp_path):
        """vocabulary.json must NOT be written when vocab list is empty."""
        from src.cli import write_json

        write_json(tmp_path, [], [], None, {"vocab"})
        assert not (tmp_path / "vocabulary.json").exists()


class TestCliWriteHumanCombinedSummary:
    """write_human combined.docx must include key_excerpts as summary_text."""

    def test_summary_text_is_passed(self):
        """source of write_human must build summary_text from key_excerpts."""
        from pathlib import Path

        text = Path("src/cli.py").read_text(encoding="utf-8")
        # The summary_text is now built from key_excerpts via a join
        assert "summary_text=summary_text" in text or 'summary_text="\\n"' in text
        assert "summary_text" in text
