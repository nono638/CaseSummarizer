"""
Dynamic Output Display Widget for LocalScribe

Displays AI-generated summaries, meta-summaries, and vocabulary CSVs.
Provides copy/save functionality for export.
The vocabulary display uses an Excel-like Treeview with frozen headers
and right-click context menu for excluding terms from future extractions.
"""

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog, Menu
import io
import csv
import os

from src.config import USER_VOCAB_EXCLUDE_PATH
from src.logging_config import debug_log


class DynamicOutputWidget(ctk.CTkFrame):
    """Widget to dynamically display AI-generated summary, meta-summary, or vocabulary CSV."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)  # Row for the dynamic content frame

        # Output Selection Dropdown
        self.output_selector_label = ctk.CTkLabel(self, text="View Output:", font=ctk.CTkFont(weight="bold"))
        self.output_selector_label.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))

        self.output_selector = ctk.CTkComboBox(self, values=["No outputs yet"], command=self._on_output_selection)
        self.output_selector.grid(row=0, column=0, sticky="e", padx=5, pady=(5, 0))
        self.output_selector.set("No outputs yet")

        # Dynamic Content Frame (to hold either Textbox or Treeview)
        self.dynamic_content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dynamic_content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=0)
        self.dynamic_content_frame.grid_columnconfigure(0, weight=1)
        self.dynamic_content_frame.grid_rowconfigure(0, weight=1)

        # Textbox for summaries
        self.summary_text_display = ctk.CTkTextbox(self.dynamic_content_frame, wrap="word")
        self.summary_text_display.grid(row=0, column=0, sticky="nsew")
        self.summary_text_display.insert("0.0", "Generated summaries and rare word lists will appear here. Select an option from the dropdown above.")

        # Treeview for CSV (initially None, created when needed)
        self.csv_treeview = None
        self.treeview_frame = None  # Frame to hold treeview and scrollbars

        # Right-click context menu for vocabulary exclusion
        self.context_menu = None
        self._selected_term = None

        # Button bar
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        self.copy_btn = ctk.CTkButton(self.button_frame, text="Copy to Clipboard", command=self.copy_to_clipboard)
        self.copy_btn.pack(side="left", padx=5)

        self.save_btn = ctk.CTkButton(self.button_frame, text="Save to File...", command=self.save_to_file)
        self.save_btn.pack(side="left", padx=5)

        # Internal storage for outputs
        self._outputs = {
            "Meta-Summary": "",
            "Rare Word List (CSV)": []
        }
        self._document_summaries = {}  # {filename: summary_text}

    def _on_output_selection(self, choice):
        """Handle selection change in the output_selector dropdown."""
        self._clear_dynamic_content()

        if choice == "No outputs yet":
            self.summary_text_display.grid(row=0, column=0, sticky="nsew")
            self.summary_text_display.delete("0.0", "end")
            self.summary_text_display.insert("0.0", "Generated summaries and rare word lists will appear here. Select an option from the dropdown above.")
        elif choice == "Meta-Summary":
            self.summary_text_display.grid(row=0, column=0, sticky="nsew")
            self.summary_text_display.delete("0.0", "end")
            self.summary_text_display.insert("0.0", self._outputs.get("Meta-Summary", "Meta-Summary not yet generated."))
        elif choice == "Rare Word List (CSV)":
            self._display_csv(self._outputs.get("Rare Word List (CSV)", []))
        elif choice.startswith("Summary for "):
            doc_name = choice.replace("Summary for ", "")
            self.summary_text_display.grid(row=0, column=0, sticky="nsew")
            self.summary_text_display.delete("0.0", "end")
            self.summary_text_display.insert("0.0", self._document_summaries.get(doc_name, f"Summary for {doc_name} not yet generated."))

    def _clear_dynamic_content(self):
        """Clears the currently displayed widget in the dynamic content frame."""
        for widget in self.dynamic_content_frame.winfo_children():
            widget.grid_remove()

    def update_outputs(self, meta_summary: str = "", vocab_csv_data: list = None, document_summaries: dict = None):
        """
        Updates the internal storage with new outputs and refreshes the dropdown.

        Args:
            meta_summary: The generated meta-summary text.
            vocab_csv_data: A list of dicts representing vocabulary data.
            document_summaries: A dictionary of {filename: summary_text}.
        """
        if meta_summary:
            self._outputs["Meta-Summary"] = meta_summary
        if vocab_csv_data is not None:
            self._outputs["Rare Word List (CSV)"] = vocab_csv_data
        if document_summaries:
            self._document_summaries.update(document_summaries)

        self._refresh_dropdown()

    def _refresh_dropdown(self):
        """Refreshes the output selection dropdown based on available outputs."""
        options = ["No outputs yet"]
        if self._outputs.get("Meta-Summary"):
            options.append("Meta-Summary")
        if self._outputs.get("Rare Word List (CSV)"):
            options.append("Rare Word List (CSV)")

        doc_summary_options = [f"Summary for {name}" for name in self._document_summaries.keys()]
        if doc_summary_options:
            doc_summary_options.sort()
            options.extend(doc_summary_options)

        self.output_selector.configure(values=options)
        if len(options) > 1:
            self.output_selector.set(options[1])
            self._on_output_selection(options[1])
        else:
            self.output_selector.set("No outputs yet")
            self._on_output_selection("No outputs yet")

    def _create_treeview_style(self):
        """Create and configure the Treeview style to match CustomTkinter dark theme."""
        style = ttk.Style()
        style.theme_use("default")

        # Main treeview styling - dark theme
        style.configure(
            "Vocab.Treeview",
            background="#2b2b2b",
            foreground="white",
            fieldbackground="#2b2b2b",
            borderwidth=0,
            rowheight=28,
            font=('Segoe UI', 10)
        )
        style.map('Vocab.Treeview', background=[('selected', '#3470b6')])

        # Header styling - slightly lighter, bold
        style.configure(
            "Vocab.Treeview.Heading",
            background="#404040",
            foreground="white",
            relief="flat",
            font=('Segoe UI', 10, 'bold'),
            padding=(8, 4)
        )
        style.map("Vocab.Treeview.Heading", background=[('active', '#505050')])

        # Scrollbar styling
        style.configure(
            "Vocab.Vertical.TScrollbar",
            background="#404040",
            troughcolor="#2b2b2b",
            borderwidth=0,
            arrowcolor="white"
        )
        style.configure(
            "Vocab.Horizontal.TScrollbar",
            background="#404040",
            troughcolor="#2b2b2b",
            borderwidth=0,
            arrowcolor="white"
        )

    def _display_csv(self, data: list):
        """
        Displays vocabulary data in an Excel-like Treeview with frozen headers.

        Args:
            data: List of dicts with keys: Term, Category, Relevance to Case, Definition
        """
        self._clear_dynamic_content()

        if not data:
            self.summary_text_display.grid(row=0, column=0, sticky="nsew")
            self.summary_text_display.delete("0.0", "end")
            self.summary_text_display.insert("0.0", "Rare Word List (CSV) not yet generated or is empty.")
            return

        # Create style if not already done
        self._create_treeview_style()

        # Create frame to hold treeview and scrollbars
        if self.treeview_frame is None:
            self.treeview_frame = ctk.CTkFrame(self.dynamic_content_frame, fg_color="#2b2b2b", corner_radius=6)

        self.treeview_frame.grid(row=0, column=0, sticky="nsew")
        self.treeview_frame.grid_columnconfigure(0, weight=1)
        self.treeview_frame.grid_rowconfigure(0, weight=1)

        # Define columns - Term is the first column now
        columns = ("Term", "Category", "Relevance", "Definition")

        # Create or reconfigure treeview
        if self.csv_treeview is None:
            self.csv_treeview = ttk.Treeview(
                self.treeview_frame,
                columns=columns,
                show="headings",
                style="Vocab.Treeview",
                selectmode="browse"
            )

            # Configure column headings and widths
            column_widths = {
                "Term": 150,
                "Category": 180,
                "Relevance": 100,
                "Definition": 350
            }

            for col in columns:
                self.csv_treeview.heading(col, text=col, anchor='w')
                self.csv_treeview.column(
                    col,
                    width=column_widths.get(col, 100),
                    minwidth=80,
                    anchor='w',
                    stretch=True if col == "Definition" else False
                )

            # Add vertical scrollbar
            vsb = ttk.Scrollbar(
                self.treeview_frame,
                orient="vertical",
                command=self.csv_treeview.yview,
                style="Vocab.Vertical.TScrollbar"
            )
            self.csv_treeview.configure(yscrollcommand=vsb.set)

            # Add horizontal scrollbar
            hsb = ttk.Scrollbar(
                self.treeview_frame,
                orient="horizontal",
                command=self.csv_treeview.xview,
                style="Vocab.Horizontal.TScrollbar"
            )
            self.csv_treeview.configure(xscrollcommand=hsb.set)

            # Grid layout
            self.csv_treeview.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            hsb.grid(row=1, column=0, sticky="ew")

            # Bind right-click for context menu
            self.csv_treeview.bind("<Button-3>", self._on_right_click)
            self.csv_treeview.bind("<Double-1>", self._on_double_click)

            # Create context menu
            self._create_context_menu()

        # Clear existing data
        self.csv_treeview.delete(*self.csv_treeview.get_children())

        # Populate with new data
        for item in data:
            if isinstance(item, dict):
                values = (
                    item.get("Term", ""),
                    item.get("Category", ""),
                    item.get("Relevance to Case", ""),
                    item.get("Definition", "")
                )
            else:
                # Handle list format (legacy)
                values = tuple(item) if len(item) >= 4 else tuple(item) + ("",) * (4 - len(item))

            self.csv_treeview.insert("", "end", values=values)

        self.csv_treeview.grid(row=0, column=0, sticky="nsew")

    def _create_context_menu(self):
        """Create right-click context menu for vocabulary table."""
        self.context_menu = Menu(self, tearoff=0, bg="#404040", fg="white",
                                  activebackground="#505050", activeforeground="white",
                                  font=('Segoe UI', 10))
        self.context_menu.add_command(
            label="Exclude this term from future lists",
            command=self._exclude_selected_term
        )
        self.context_menu.add_separator()
        self.context_menu.add_command(
            label="Copy term",
            command=self._copy_selected_term
        )

    def _on_right_click(self, event):
        """Handle right-click on treeview to show context menu."""
        # Identify the row under cursor
        item_id = self.csv_treeview.identify_row(event.y)
        if item_id:
            # Select the row
            self.csv_treeview.selection_set(item_id)
            # Get the term value (first column)
            values = self.csv_treeview.item(item_id, 'values')
            if values:
                self._selected_term = values[0]  # Term is first column
                # Show context menu at cursor position
                try:
                    self.context_menu.tk_popup(event.x_root, event.y_root)
                finally:
                    self.context_menu.grab_release()

    def _on_double_click(self, event):
        """Handle double-click to copy the full definition."""
        item_id = self.csv_treeview.identify_row(event.y)
        if item_id:
            values = self.csv_treeview.item(item_id, 'values')
            if values and len(values) >= 4:
                definition = values[3]  # Definition is fourth column
                if definition and definition != "N/A":
                    self.clipboard_clear()
                    self.clipboard_append(definition)
                    # Brief visual feedback could be added here

    def _exclude_selected_term(self):
        """Exclude the selected term from future vocabulary extractions."""
        if not self._selected_term:
            return

        term = self._selected_term
        lower_term = term.lower().strip()

        # Confirm with user
        result = messagebox.askyesno(
            "Exclude Term",
            f"Exclude '{term}' from future rare word lists?\n\n"
            f"This will also exclude case variations like '{term.upper()}' and '{term.title()}'.\n\n"
            "You can undo this by editing:\n"
            f"{USER_VOCAB_EXCLUDE_PATH}",
            icon="question"
        )

        if not result:
            return

        # Add to exclusion file
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(USER_VOCAB_EXCLUDE_PATH), exist_ok=True)

            # Append to file
            with open(USER_VOCAB_EXCLUDE_PATH, 'a', encoding='utf-8') as f:
                f.write(f"{lower_term}\n")

            debug_log(f"[VOCAB UI] Added '{term}' to user exclusion list at {USER_VOCAB_EXCLUDE_PATH}")

            # Remove from current display
            selected = self.csv_treeview.selection()
            if selected:
                self.csv_treeview.delete(selected[0])

                # Also remove from internal data
                self._outputs["Rare Word List (CSV)"] = [
                    item for item in self._outputs.get("Rare Word List (CSV)", [])
                    if isinstance(item, dict) and item.get("Term", "").lower() != lower_term
                ]

            messagebox.showinfo(
                "Term Excluded",
                f"'{term}' will not appear in future rare word lists.\n\n"
                "Note: This takes effect on the next vocabulary extraction."
            )

        except Exception as e:
            debug_log(f"[VOCAB UI] Failed to save exclusion: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to save exclusion: {e}\n\n"
                "Please check file permissions."
            )

    def _copy_selected_term(self):
        """Copy the selected term to clipboard."""
        if self._selected_term:
            self.clipboard_clear()
            self.clipboard_append(self._selected_term)

    def get_current_content_for_export(self):
        """Returns the currently displayed content for copy/save operations."""
        current_choice = self.output_selector.get()
        if current_choice == "Meta-Summary":
            return self._outputs.get("Meta-Summary", "")
        elif current_choice == "Rare Word List (CSV)":
            # Convert list of dicts to CSV string with Term column
            data = self._outputs.get("Rare Word List (CSV)", [])
            if not data:
                return ""
            output = io.StringIO()
            writer = csv.writer(output)
            # Write header
            writer.writerow(["Term", "Category", "Relevance to Case", "Definition"])
            # Write data
            for item in data:
                if isinstance(item, dict):
                    writer.writerow([
                        item.get("Term", ""),
                        item.get("Category", ""),
                        item.get("Relevance to Case", ""),
                        item.get("Definition", "")
                    ])
                else:
                    writer.writerow(item)
            return output.getvalue()
        elif current_choice.startswith("Summary for "):
            doc_name = current_choice.replace("Summary for ", "")
            return self._document_summaries.get(doc_name, "")
        return ""

    def copy_to_clipboard(self):
        """Copy currently displayed content to clipboard."""
        content = self.get_current_content_for_export()
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo("Copied", "Content copied to clipboard.")
        else:
            messagebox.showwarning("Empty", "No content to copy.")

    def save_to_file(self):
        """Save currently displayed content to file."""
        content = self.get_current_content_for_export()
        if not content:
            messagebox.showwarning("Empty", "No content to save.")
            return

        current_choice = self.output_selector.get()
        default_filename = "output"
        filetypes = [("All Files", "*.*")]

        if current_choice == "Meta-Summary":
            default_filename = "meta_summary.txt"
            filetypes = [("Text Files", "*.txt"), ("All Files", "*.*")]
        elif current_choice == "Rare Word List (CSV)":
            default_filename = "rare_word_list.csv"
            filetypes = [("CSV Files", "*.csv"), ("All Files", "*.*")]
        elif current_choice.startswith("Summary for "):
            doc_name = current_choice.replace("Summary for ", "")
            default_filename = f"{doc_name}_summary.txt"
            filetypes = [("Text Files", "*.txt"), ("All Files", "*.*")]

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=filetypes,
            initialfile=default_filename,
            title="Save Output"
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Saved", f"Output saved to {filepath}")
