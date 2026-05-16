"""
Shared HTML fragment builders for vocabulary and Q&A exports.

Both html_builder.py (standalone) and combined_html_builder.py (tabbed) use
the same row/header/toggle/Q&A structures, with small differences in glyph
encoding and a "(required)" suffix on the standalone protected-column toggle.

This module provides parameterized builders that produce the exact existing
markup for both, so the two builders share one source of truth for the
vocab table rows and Q&A item bodies.

The wrapper containers (controls bar, search input ids, count display ids)
are NOT consolidated here because the two builders use different element
ids and surrounding markup — those remain in their respective builders.
"""

from src.config import COLUMN_DEFINITIONS, PROTECTED_COLUMNS
from src.core.vocab_schema import VF

# Column list shared by both builders. Excludes Keep/Skip feedback columns
# which are GUI-only and never exported.
VOCAB_HTML_COLUMNS = [
    (c.name, c.data_key) for c in COLUMN_DEFINITIONS if c.name not in (VF.KEEP, VF.SKIP)
]


def _escape(text) -> str:
    """Escape HTML special characters."""
    import html

    return html.escape(str(text)) if text is not None and text != "" else ""


def build_vocab_toggles(visible_columns: list[str], protected_required: bool) -> list[str]:
    """
    Build the per-column toggle <label> entries.

    Args:
        visible_columns: Columns initially visible.
        protected_required: If True, append ' (required)' to protected column
            labels (the standalone builder does this; combined does not).

    Returns:
        A list of HTML <label>...</label> strings, in column order.
    """
    parts = []
    suffix = " (required)" if protected_required else ""
    for col_name, _ in VOCAB_HTML_COLUMNS:
        col_id = col_name.replace(" ", "").replace("#", "").replace("/", "")
        is_visible = col_name in visible_columns
        if col_name in PROTECTED_COLUMNS:
            parts.append(
                f'<label><input type="checkbox" id="col-{col_id}" '
                f"checked disabled> {col_name}{suffix}</label>"
            )
        else:
            checked = " checked" if is_visible else ""
            parts.append(
                f'<label><input type="checkbox" id="col-{col_id}" '
                f"onchange=\"toggleColumn('{col_name}')\"{checked}> {col_name}</label>"
            )
    return parts


def build_vocab_headers(visible_columns: list[str], indent: str, arrow_glyph: str) -> str:
    """
    Build the <th> tags for the vocab table.

    Args:
        visible_columns: Columns initially visible.
        indent: Leading whitespace per <th> line (different between builders).
        arrow_glyph: The sort arrow markup, e.g. '▼' or '&#x25BC;'.

    Returns:
        Newline-joined <th> tags as a single string.
    """
    header_parts = []
    for i, (col_name, _) in enumerate(VOCAB_HTML_COLUMNS):
        hidden_class = "" if col_name in visible_columns else ' class="col-hidden"'
        header_parts.append(
            f'{indent}<th onclick="sortTable({i})"{hidden_class}>'
            f'{col_name} <span class="sort-arrow">{arrow_glyph}</span></th>'
        )
    return "\n".join(header_parts)


def build_vocab_rows(vocab_data: list[dict], visible_columns: list[str], indent: str) -> str:
    """
    Build the <tr>...<td>... rows for the vocab table.

    Args:
        vocab_data: List of vocabulary entry dicts.
        visible_columns: Columns initially visible.
        indent: Leading whitespace per <tr> line.

    Returns:
        Newline-joined <tr> tags as a single string.
    """
    rows = []
    for v in vocab_data:
        is_person = v.get(VF.IS_PERSON, "") == VF.YES
        row_class = ' class="person"' if is_person else ""
        cells = []
        for col_name, data_key in VOCAB_HTML_COLUMNS:
            hidden_class = "" if col_name in visible_columns else ' class="col-hidden"'
            value = v.get(data_key, "")
            cells.append(f"<td{hidden_class}>{_escape(value)}</td>")
        rows.append(f"{indent}<tr{row_class}>{''.join(cells)}</tr>")
    return "\n".join(rows)


def build_qa_item(result, index: int, onclick_fn: str, hide_glyph: str) -> str:
    """
    Build a single Q&A item block.

    Args:
        result: SemanticResult-like object with question, citation,
            source_summary, quick_answer attributes.
        index: 1-based index for the Q{N}: header label.
        onclick_fn: Name of the JS function bound to the header click,
            e.g. 'toggleItem' (standalone) or 'toggleQAItem' (combined).
        hide_glyph: The collapsed/expanded arrow text, e.g. '▼ Hide'
            (standalone) or '&#x25BC; Hide' (combined).

    Returns:
        A complete <div class="qa-item"> ... </div> block.
    """
    citation = _escape(result.citation) if result.citation else "(no citation)"
    source = _escape(result.source_summary) if result.source_summary else "(source unknown)"
    q_truncated = _escape(result.question[:80])
    ellipsis = "..." if len(result.question) > 80 else ""

    answer_block = ""
    if result.quick_answer:
        answer_html = _escape(result.quick_answer)
        answer_block = (
            f'                <div class="label">Answer</div>\n'
            f'                <div class="answer">{answer_html}</div>'
        )

    return f"""        <div class="qa-item">
            <div class="qa-header" onclick="{onclick_fn}(this)">
                <span>Q{index}: {q_truncated}{ellipsis}</span>
                <span class="toggle">{hide_glyph}</span>
            </div>
            <div class="qa-content">
                <div class="question">{_escape(result.question)}</div>
{answer_block}
                <div class="label">Citation</div>
                <div class="citation">{citation}</div>
                <div class="label">Source</div>
                <div class="source">{source}</div>
            </div>
        </div>"""
