"""
Behavioral tests for the headless CLI helpers in src/cli.py.

Coverage focus:
- collect_inputs: file vs directory vs missing, supported-extension filtering,
  recursive globbing, empty-input failure.
- drain: drains a queue without blocking, preserves order, copes with empties.
- write_json: vocabulary/excerpts gating, search.json written when search_result present.
- write_human: file gating and summary_text wiring (uses real export, no mocks).
- parse_args: required arguments, --only repeatable, --format choices.

These tests run synchronously and never spawn worker processes.
"""

import json
import sys
from queue import Queue

import pytest

# ---------------------------------------------------------------------------
# collect_inputs
# ---------------------------------------------------------------------------


class TestCollectInputs:
    """collect_inputs expands files and directories to a flat path list."""

    def test_single_file_kept(self, tmp_path):
        """An explicit file path is returned verbatim."""
        from src.cli import collect_inputs

        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4")
        result = collect_inputs([str(f)])
        assert result == [str(f)]

    def test_directory_globbed_recursively(self, tmp_path):
        """A directory contributes every supported file underneath it."""
        from src.cli import collect_inputs

        (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
        sub = tmp_path / "nested"
        sub.mkdir()
        (sub / "b.txt").write_text("hello")
        # Unsupported extension must be filtered out.
        (tmp_path / "ignore.xyz").write_text("nope")

        result = collect_inputs([str(tmp_path)])
        assert any(p.endswith("a.pdf") for p in result)
        assert any(p.endswith("b.txt") for p in result)
        assert not any(p.endswith("ignore.xyz") for p in result)
        assert len(result) == 2

    def test_unsupported_extension_excluded(self, tmp_path):
        """Files with non-allowed extensions are skipped under directory expansion."""
        from src.cli import collect_inputs

        (tmp_path / "weird.html").write_text("nope")
        (tmp_path / "ok.txt").write_text("yes")
        result = collect_inputs([str(tmp_path)])
        assert result == [str(tmp_path / "ok.txt")]

    def test_missing_path_warns_and_continues(self, tmp_path, capsys):
        """A nonexistent path logs a warning but other inputs still resolve."""
        from src.cli import collect_inputs

        good = tmp_path / "doc.txt"
        good.write_text("x")
        bad = str(tmp_path / "missing.txt")
        result = collect_inputs([bad, str(good)])
        captured = capsys.readouterr()
        assert "warning" in captured.err.lower()
        assert "missing.txt" in captured.err
        assert result == [str(good)]

    def test_no_supported_files_raises_systemexit(self, tmp_path):
        """Empty result must raise SystemExit so CLI bails out with a message."""
        from src.cli import collect_inputs

        # Directory exists but contains nothing supported.
        with pytest.raises(SystemExit):
            collect_inputs([str(tmp_path)])

    def test_supported_extensions_match_documented_set(self):
        """SUPPORTED_EXTS must include the documented file types."""
        from src.cli import SUPPORTED_EXTS

        for ext in (".pdf", ".txt", ".rtf", ".docx", ".png", ".jpg", ".jpeg"):
            assert ext in SUPPORTED_EXTS

    def test_extension_match_is_case_insensitive(self, tmp_path):
        """Suffix comparison normalizes via .lower(), so .PDF must be accepted."""
        from src.cli import collect_inputs

        f = tmp_path / "UPPER.PDF"
        f.write_bytes(b"%PDF-1.4")
        result = collect_inputs([str(tmp_path)])
        assert str(f) in result


# ---------------------------------------------------------------------------
# drain
# ---------------------------------------------------------------------------


class TestDrain:
    """drain pulls every queued message non-blockingly, in FIFO order."""

    def test_drain_empty_queue_returns_empty_list(self):
        """A fresh queue produces an empty list, not a block."""
        from src.cli import drain

        assert drain(Queue()) == []

    def test_drain_preserves_order(self):
        """Messages come out in put-order."""
        from src.cli import drain

        q: Queue = Queue()
        q.put(("a", 1))
        q.put(("b", 2))
        q.put(("c", 3))
        assert drain(q) == [("a", 1), ("b", 2), ("c", 3)]

    def test_drain_leaves_queue_empty(self):
        """After drain, the queue has no remaining items."""
        from src.cli import drain

        q: Queue = Queue()
        q.put(("x", None))
        drain(q)
        assert q.empty()


# ---------------------------------------------------------------------------
# write_json
# ---------------------------------------------------------------------------


class TestWriteJson:
    """write_json gates files on data presence and the --only set."""

    def test_vocabulary_written_when_present_and_requested(self, tmp_path):
        """Non-empty vocab + 'vocab' in only -> vocabulary.json appears."""
        from src.cli import write_json

        vocab = [{"Term": "negligence", "Quality Score": 5}]
        write_json(tmp_path, vocab, [], None, {"vocab"})
        target = tmp_path / "vocabulary.json"
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data == vocab

    def test_vocabulary_skipped_when_not_in_only(self, tmp_path):
        """Empty 'only' set -> no vocabulary.json even when vocab is present."""
        from src.cli import write_json

        write_json(tmp_path, [{"Term": "x"}], [], None, set())
        assert not (tmp_path / "vocabulary.json").exists()

    def test_excerpts_always_written_when_requested(self, tmp_path):
        """excerpts.json must be created even when the list is empty (truthy gate)."""
        from src.cli import write_json

        write_json(tmp_path, [], [], None, {"excerpts"})
        # Empty excerpts list still produces the file because the gate only checks 'in only'
        target = tmp_path / "excerpts.json"
        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8")) == []

    def test_search_json_independent_of_only(self, tmp_path):
        """search.json is written whenever a search_result is supplied."""
        from types import SimpleNamespace

        from src.cli import write_json

        search = SimpleNamespace(
            question="what hurts",
            citation="lower back",
            source_summary="report.pdf p2",
            relevance=0.8,
        )
        write_json(tmp_path, [], [], search, set())  # only is empty!
        target = tmp_path / "search.json"
        assert target.exists()
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload["question"] == "what hurts"
        assert payload["citation"] == "lower back"
        assert payload["source"] == "report.pdf p2"
        assert payload["relevance"] == 0.8

    def test_search_json_absent_when_no_result(self, tmp_path):
        """No search_result -> no search.json."""
        from src.cli import write_json

        write_json(tmp_path, [], [], None, {"vocab", "excerpts", "combined"})
        assert not (tmp_path / "search.json").exists()


# ---------------------------------------------------------------------------
# write_human
# ---------------------------------------------------------------------------


class TestWriteHuman:
    """write_human creates Word/TXT outputs based on the --only set."""

    def test_vocab_word_doc_created(self, tmp_path):
        """Vocab present + 'vocab' in only -> vocabulary.docx file appears."""
        from src.cli import write_human

        vocab = [{"Term": "negligence", "Quality Score": 5, "Found By": "BM25"}]
        write_human(tmp_path, vocab, [], None, {"vocab"})
        assert (tmp_path / "vocabulary.docx").exists()
        # File must contain something — Word docs are at least a few KB.
        assert (tmp_path / "vocabulary.docx").stat().st_size > 1000

    def test_excerpts_text_file_created(self, tmp_path):
        """key_excerpts.txt is written with score formatting."""
        from src.cli import write_human

        excerpts = [
            {"source_file": "a.pdf", "score": 0.91, "text": "first chunk", "position": 0},
            {"source_file": "b.pdf", "score": 0.42, "text": "second chunk", "position": 1},
        ]
        write_human(tmp_path, [], excerpts, None, {"excerpts"})
        target = tmp_path / "key_excerpts.txt"
        assert target.exists()
        body = target.read_text(encoding="utf-8")
        # Both excerpts are present, separated by --- delimiters.
        assert "first chunk" in body
        assert "second chunk" in body
        assert "a.pdf" in body
        assert "b.pdf" in body
        assert "score=0.910" in body

    def test_excerpts_skipped_when_empty(self, tmp_path):
        """An empty excerpts list must NOT create the file."""
        from src.cli import write_human

        write_human(tmp_path, [], [], None, {"excerpts"})
        assert not (tmp_path / "key_excerpts.txt").exists()

    def test_vocab_skipped_when_not_in_only(self, tmp_path):
        """'vocab' missing from only -> no vocabulary.docx even with data."""
        from src.cli import write_human

        write_human(tmp_path, [{"Term": "x"}], [], None, {"excerpts"})
        assert not (tmp_path / "vocabulary.docx").exists()


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


class TestParseArgs:
    """parse_args interprets the CLI flag surface."""

    def _run(self, argv, monkeypatch):
        """Helper: invoke parse_args() with patched sys.argv."""
        monkeypatch.setattr(sys, "argv", ["caseprepd-cli"] + argv)
        from src.cli import parse_args

        return parse_args()

    def test_input_and_output_required(self, monkeypatch):
        """Missing --input/--output causes argparse to SystemExit."""
        monkeypatch.setattr(sys, "argv", ["caseprepd-cli"])
        from src.cli import parse_args

        with pytest.raises(SystemExit):
            parse_args()

    def test_default_format_is_human(self, monkeypatch):
        """--format defaults to 'human' when omitted."""
        ns = self._run(["--input", "in", "--output", "out"], monkeypatch)
        assert ns.format == "human"

    def test_only_is_repeatable_into_list(self, monkeypatch):
        """--only used multiple times accumulates into a list."""
        ns = self._run(
            ["--input", "a", "--output", "b", "--only", "vocab", "--only", "combined"],
            monkeypatch,
        )
        assert ns.only == ["vocab", "combined"]

    def test_only_default_is_none(self, monkeypatch):
        """Without --only, the namespace value is None (CLI fills defaults later)."""
        ns = self._run(["--input", "a", "--output", "b"], monkeypatch)
        assert ns.only is None

    def test_query_default_is_none(self, monkeypatch):
        """--query defaults to None."""
        ns = self._run(["--input", "a", "--output", "b"], monkeypatch)
        assert ns.query is None

    def test_invalid_format_choice_rejected(self, monkeypatch):
        """--format=xml is not in the choices list."""
        monkeypatch.setattr(
            sys, "argv", ["caseprepd-cli", "--input", "a", "--output", "b", "--format", "xml"]
        )
        from src.cli import parse_args

        with pytest.raises(SystemExit):
            parse_args()

    def test_verbose_flag_sets_true(self, monkeypatch):
        """-v / --verbose sets the verbose attribute to True."""
        ns = self._run(["--input", "a", "--output", "b", "-v"], monkeypatch)
        assert ns.verbose is True


# ---------------------------------------------------------------------------
# run_query
# ---------------------------------------------------------------------------


class TestRunQuery:
    """run_query short-circuits when no semantic index is available."""

    def test_no_semantic_data_returns_none(self, capsys):
        """Missing semantic_data -> warning to stderr + None return."""
        from src.cli import run_query

        result = run_query(None, "what happened")
        assert result is None
        assert "warning" in capsys.readouterr().err.lower()

    def test_empty_semantic_data_returns_none(self, capsys):
        """Empty dict is falsy -> short-circuit just like None."""
        from src.cli import run_query

        assert run_query({}, "x") is None
