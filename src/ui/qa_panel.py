"""
Q&A Panel Widget for LocalScribe.

Displays Q&A results from vector search in a plain text format with:
- Scrollable results display (text)
- Per-result include/exclude toggles (Treeview checkboxes)
- Action buttons: Edit Questions, Ask More Questions, Export TXT
- Collapsible follow-up question input pane

The panel supports both automatic default questions and user-initiated
follow-up questions through the "Ask More Questions" feature.
"""

from pathlib import Path
from tkinter import Menu, filedialog, messagebox, ttk
from typing import Callable

import customtkinter as ctk

from src.config import DEBUG_MODE
from src.logging_config import debug_log
from src.qa.qa_orchestrator import QAResult

# Unicode checkbox icons for toggle display
CHECK_ICON = "☑"  # U+2611 Ballot Box with Check
UNCHECK_ICON = "☐"  # U+2610 Ballot Box


class QAPanel(ctk.CTkFrame):
    """
    Q&A display panel with results, toggles, and follow-up input.

    Features:
    - Plain text display of Q&A pairs (scrollable)
    - Treeview-based toggle list for include/exclude checkboxes
    - "Edit Questions" button to open question editor
    - "Ask More Questions" button to reveal follow-up input
    - "Export TXT" button to save selected Q&As
    - Collapsible follow-up question pane

    Example:
        panel = QAPanel(parent)
        panel.display_results(qa_results)

        # Handle follow-up questions
        panel.set_followup_callback(lambda q: orchestrator.ask_followup(q))
    """

    def __init__(
        self,
        master,
        on_edit_questions: Callable | None = None,
        on_ask_followup: Callable[[str], QAResult | None] | None = None,
        **kwargs
    ):
        """
        Initialize Q&A panel.

        Args:
            master: Parent widget
            on_edit_questions: Callback when "Edit Questions" is clicked
            on_ask_followup: Callback(question_text) -> QAResult for follow-ups
        """
        super().__init__(master, **kwargs)

        self.on_edit_questions = on_edit_questions
        self.on_ask_followup = on_ask_followup

        # Results storage
        self._results: list[QAResult] = []

        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Results area expands

        # Build UI components
        self._create_header()
        self._create_results_area()
        self._create_toggle_list()
        self._create_button_bar()
        self._create_followup_pane()

        # Apply Treeview styling
        self._create_toggle_style()

        if DEBUG_MODE:
            debug_log("[QAPanel] Initialized")

    def _create_header(self):
        """Create header with title and info."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))

        title = ctk.CTkLabel(
            header,
            text="Document Q&A",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title.pack(side="left")

        self.info_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#aaaaaa"
        )
        self.info_label.pack(side="right")

    def _create_results_area(self):
        """Create main results display area."""
        # Frame for results display and toggle list side by side
        results_frame = ctk.CTkFrame(self, fg_color="transparent")
        results_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        results_frame.grid_columnconfigure(0, weight=3)  # Text area gets more space
        results_frame.grid_columnconfigure(1, weight=1)  # Toggle list
        results_frame.grid_rowconfigure(0, weight=1)

        # Text display for Q&A content
        self.results_text = ctk.CTkTextbox(
            results_frame,
            wrap="word",
            font=ctk.CTkFont(size=11)
        )
        self.results_text.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        # Initial placeholder text
        self._show_placeholder()

    def _create_toggle_list(self):
        """Create Treeview-based toggle list for include/exclude."""
        # Get the results_frame (parent of results_text)
        results_frame = self.results_text.master

        # Frame for toggle list
        toggle_frame = ctk.CTkFrame(results_frame, fg_color="#2b2b2b", corner_radius=6)
        toggle_frame.grid(row=0, column=1, sticky="nsew")
        toggle_frame.grid_columnconfigure(0, weight=1)
        toggle_frame.grid_rowconfigure(1, weight=1)

        # Label
        toggle_label = ctk.CTkLabel(
            toggle_frame,
            text="Include in Export:",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        toggle_label.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 2))

        # Treeview for checkboxes
        self.toggle_tree = ttk.Treeview(
            toggle_frame,
            columns=("include", "question"),
            show="tree",  # Hide column headers
            style="QAToggle.Treeview",
            selectmode="browse",
            height=10
        )

        # Configure columns
        self.toggle_tree.column("#0", width=0, stretch=False)  # Hide tree column
        self.toggle_tree.column("include", width=25, stretch=False, anchor="center")
        self.toggle_tree.column("question", width=150, stretch=True, anchor="w")

        self.toggle_tree.grid(row=1, column=0, sticky="nsew", padx=2, pady=2)

        # Scrollbar for toggle list
        toggle_scroll = ttk.Scrollbar(
            toggle_frame,
            orient="vertical",
            command=self.toggle_tree.yview
        )
        self.toggle_tree.configure(yscrollcommand=toggle_scroll.set)
        toggle_scroll.grid(row=1, column=1, sticky="ns")

        # Bind click to toggle
        self.toggle_tree.bind("<Button-1>", self._on_toggle_click)

    def _create_toggle_style(self):
        """Create Treeview style for toggle list."""
        style = ttk.Style()
        style.theme_use("default")

        style.configure(
            "QAToggle.Treeview",
            background="#2b2b2b",
            foreground="white",
            fieldbackground="#2b2b2b",
            borderwidth=0,
            rowheight=22,
            font=('Segoe UI', 10)
        )
        style.map('QAToggle.Treeview', background=[('selected', '#3470b6')])

    def _create_button_bar(self):
        """Create action buttons bar."""
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        # Edit Questions button
        self.edit_btn = ctk.CTkButton(
            button_frame,
            text="⚙ Edit Questions",
            command=self._on_edit_click,
            width=130
        )
        self.edit_btn.pack(side="left", padx=(0, 5))

        # Ask More Questions button
        self.ask_more_btn = ctk.CTkButton(
            button_frame,
            text="Ask More Questions",
            command=self._toggle_followup_pane,
            width=140
        )
        self.ask_more_btn.pack(side="left", padx=5)

        # Export TXT button
        self.export_btn = ctk.CTkButton(
            button_frame,
            text="Export TXT",
            command=self._export_to_file,
            width=100
        )
        self.export_btn.pack(side="right", padx=5)

        # Select All / Deselect All buttons
        self.select_all_btn = ctk.CTkButton(
            button_frame,
            text="Select All",
            command=lambda: self._set_all_include(True),
            width=80,
            fg_color="#2d5a87"
        )
        self.select_all_btn.pack(side="right", padx=5)

        self.deselect_all_btn = ctk.CTkButton(
            button_frame,
            text="Deselect All",
            command=lambda: self._set_all_include(False),
            width=90,
            fg_color="#555555"
        )
        self.deselect_all_btn.pack(side="right", padx=5)

    def _create_followup_pane(self):
        """Create collapsible follow-up question input pane."""
        self.followup_frame = ctk.CTkFrame(self, fg_color="#333333", corner_radius=6)
        # Initially hidden
        self.followup_visible = False

        # Input field
        self.followup_entry = ctk.CTkEntry(
            self.followup_frame,
            placeholder_text="Type your question here...",
            width=400
        )
        self.followup_entry.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=10)

        # Bind Enter key
        self.followup_entry.bind("<Return>", lambda e: self._submit_followup())

        # Ask button
        self.followup_ask_btn = ctk.CTkButton(
            self.followup_frame,
            text="Ask",
            command=self._submit_followup,
            width=80
        )
        self.followup_ask_btn.pack(side="right", padx=(5, 10), pady=10)

    def _show_placeholder(self):
        """Show placeholder text when no results."""
        self.results_text.configure(state="normal")
        self.results_text.delete("0.0", "end")
        self.results_text.insert(
            "0.0",
            "Q&A results will appear here after document processing.\n\n"
            "The system will automatically ask default questions about your documents "
            "using vector similarity search."
        )
        self.results_text.configure(state="disabled")

    def display_results(self, results: list[QAResult]):
        """
        Display Q&A results in the panel.

        Args:
            results: List of QAResult objects to display
        """
        self._results = results

        # Update text display
        self._render_text_display()

        # Update toggle list
        self._render_toggle_list()

        # Update info label
        included = sum(1 for r in results if r.include_in_export)
        self.info_label.configure(text=f"{included}/{len(results)} selected for export")

        if DEBUG_MODE:
            debug_log(f"[QAPanel] Displaying {len(results)} results")

    def _render_text_display(self):
        """Render Q&A results as formatted text."""
        self.results_text.configure(state="normal")
        self.results_text.delete("0.0", "end")

        if not self._results:
            self._show_placeholder()
            return

        lines = []
        lines.append("═" * 60)
        lines.append("DOCUMENT Q&A RESULTS")
        lines.append("═" * 60)
        lines.append("")

        for i, result in enumerate(self._results, 1):
            # Question
            lines.append(f"Q{i}: {result.question}")
            lines.append("")

            # Answer
            lines.append(f"A: {result.answer}")

            # Source citation if available
            if result.source_summary:
                lines.append(f"   [Source: {result.source_summary}]")

            # Export status indicator
            status = CHECK_ICON if result.include_in_export else UNCHECK_ICON
            lines.append(f"\n{status} Include in export")

            lines.append("")
            lines.append("─" * 60)
            lines.append("")

        self.results_text.insert("0.0", "\n".join(lines))
        self.results_text.configure(state="disabled")

    def _render_toggle_list(self):
        """Render toggle list with checkboxes."""
        # Clear existing items
        self.toggle_tree.delete(*self.toggle_tree.get_children())

        for i, result in enumerate(self._results):
            icon = CHECK_ICON if result.include_in_export else UNCHECK_ICON
            # Truncate question for display
            question_display = result.question[:40] + "..." if len(result.question) > 40 else result.question

            self.toggle_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(icon, question_display)
            )

    def _on_toggle_click(self, event):
        """Handle click on toggle list to toggle include_in_export."""
        item_id = self.toggle_tree.identify_row(event.y)
        if not item_id:
            return

        try:
            index = int(item_id)
            if 0 <= index < len(self._results):
                # Toggle the flag
                result = self._results[index]
                result.include_in_export = not result.include_in_export

                # Update display
                icon = CHECK_ICON if result.include_in_export else UNCHECK_ICON
                values = self.toggle_tree.item(item_id, 'values')
                self.toggle_tree.item(item_id, values=(icon, values[1]))

                # Update text display
                self._render_text_display()

                # Update info label
                included = sum(1 for r in self._results if r.include_in_export)
                self.info_label.configure(text=f"{included}/{len(self._results)} selected for export")

                if DEBUG_MODE:
                    debug_log(f"[QAPanel] Toggled Q{index + 1}: include={result.include_in_export}")

        except (ValueError, IndexError):
            pass

    def _set_all_include(self, include: bool):
        """Set include_in_export for all results."""
        for result in self._results:
            result.include_in_export = include

        self._render_toggle_list()
        self._render_text_display()

        included = sum(1 for r in self._results if r.include_in_export)
        self.info_label.configure(text=f"{included}/{len(self._results)} selected for export")

    def _toggle_followup_pane(self):
        """Show/hide the follow-up question input pane."""
        if self.followup_visible:
            self.followup_frame.grid_remove()
            self.ask_more_btn.configure(text="Ask More Questions")
            self.followup_visible = False
        else:
            self.followup_frame.grid(row=3, column=0, sticky="ew", padx=5, pady=(0, 5))
            self.ask_more_btn.configure(text="Hide Question Input")
            self.followup_visible = True
            self.followup_entry.focus()

    def _submit_followup(self):
        """Submit a follow-up question."""
        question = self.followup_entry.get().strip()
        if not question:
            return

        if self.on_ask_followup is None:
            messagebox.showwarning(
                "Not Available",
                "Follow-up questions are not available. "
                "Please process a document first."
            )
            return

        # Clear entry
        self.followup_entry.delete(0, "end")

        # Disable button while processing
        self.followup_ask_btn.configure(state="disabled", text="Asking...")

        try:
            # Call the callback (should run async in real implementation)
            result = self.on_ask_followup(question)

            if result:
                # Add to results
                self._results.append(result)
                self.display_results(self._results)

                if DEBUG_MODE:
                    debug_log(f"[QAPanel] Added follow-up: {question[:30]}...")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to ask question: {e}")
            debug_log(f"[QAPanel] Follow-up error: {e}")

        finally:
            self.followup_ask_btn.configure(state="normal", text="Ask")

    def _on_edit_click(self):
        """Handle Edit Questions button click."""
        if self.on_edit_questions:
            self.on_edit_questions()
        else:
            messagebox.showinfo(
                "Edit Questions",
                "Question editor will be available in Settings > Q&A > Edit Default Questions"
            )

    def _export_to_file(self):
        """Export selected Q&A results to TXT file."""
        exportable = [r for r in self._results if r.include_in_export]

        if not exportable:
            messagebox.showwarning(
                "No Q&A Selected",
                "Select at least one Q&A pair to export.\n\n"
                "Click the checkboxes in the toggle list on the right."
            )
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="document_qa.txt",
            title="Export Q&A Results"
        )

        if not filepath:
            return

        try:
            content = self._format_export(exportable)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)

            messagebox.showinfo("Exported", f"Q&A results saved to:\n{filepath}")
            debug_log(f"[QAPanel] Exported {len(exportable)} Q&A pairs to {filepath}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to save file: {e}")
            debug_log(f"[QAPanel] Export error: {e}")

    def _format_export(self, results: list[QAResult]) -> str:
        """
        Format results for TXT export.

        Args:
            results: List of QAResult objects to export

        Returns:
            Formatted text string
        """
        lines = [
            "=" * 60,
            "DOCUMENT Q&A SUMMARY",
            "=" * 60,
            ""
        ]

        for i, result in enumerate(results, 1):
            lines.append(f"Q{i}: {result.question}")
            lines.append(f"A: {result.answer}")
            if result.source_summary:
                lines.append(f"   [Source: {result.source_summary}]")
            lines.append("")

        return "\n".join(lines)

    def get_export_content(self) -> str:
        """
        Get exportable content as string.

        Used by DynamicOutputWidget for copy/save operations.

        Returns:
            Formatted text of selected Q&A pairs
        """
        exportable = [r for r in self._results if r.include_in_export]
        if not exportable:
            return ""
        return self._format_export(exportable)

    def set_followup_callback(self, callback: Callable[[str], QAResult | None]):
        """
        Set callback for follow-up questions.

        Args:
            callback: Function(question_text) -> QAResult
        """
        self.on_ask_followup = callback

    def set_edit_callback(self, callback: Callable):
        """
        Set callback for Edit Questions button.

        Args:
            callback: Function to call when Edit is clicked
        """
        self.on_edit_questions = callback

    def clear(self):
        """Clear all results and reset display."""
        self._results = []
        self._show_placeholder()
        self.toggle_tree.delete(*self.toggle_tree.get_children())
        self.info_label.configure(text="")
