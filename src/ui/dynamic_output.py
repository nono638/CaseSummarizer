"""
Dynamic Output Display Widget for LocalScribe

Displays AI-generated summaries, meta-summaries, and vocabulary CSVs.
Provides copy/save functionality for export.
"""

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import io
import csv


class DynamicOutputWidget(ctk.CTkFrame):
    """Widget to dynamically display AI-generated summary, meta-summary, or vocabulary CSV."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1) # Row for the dynamic content frame

        # Output Selection Dropdown
        self.output_selector_label = ctk.CTkLabel(self, text="View Output:", font=ctk.CTkFont(weight="bold"))
        self.output_selector_label.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))

        self.output_selector = ctk.CTkComboBox(self, values=["No outputs yet"], command=self._on_output_selection)
        self.output_selector.grid(row=0, column=0, sticky="e", padx=5, pady=(5, 0))
        self.output_selector.set("No outputs yet") # Initial placeholder

        # Dynamic Content Frame (to hold either Textbox or Treeview)
        self.dynamic_content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dynamic_content_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=0)
        self.dynamic_content_frame.grid_columnconfigure(0, weight=1)
        self.dynamic_content_frame.grid_rowconfigure(0, weight=1)

        # Textbox for summaries
        self.summary_text_display = ctk.CTkTextbox(self.dynamic_content_frame, wrap="word")
        self.summary_text_display.grid(row=0, column=0, sticky="nsew")
        self.summary_text_display.insert("0.0", "Generated summaries and rare word lists will appear here. Select an option from the dropdown above.")

        # Treeview for CSV (initially hidden)
        self.csv_treeview = None # Will be initialized when CSV data is loaded

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
        self._document_summaries = {} # {filename: summary_text}

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
            widget.grid_remove() # Use grid_remove for widgets managed by grid

    def update_outputs(self, meta_summary: str = "", vocab_csv_data: list = None, document_summaries: dict = None):
        """
        Updates the internal storage with new outputs and refreshes the dropdown.

        Args:
            meta_summary: The generated meta-summary text.
            vocab_csv_data: A list of lists representing the CSV data.
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
            self.output_selector.set(options[1]) # Select first available real output
            self._on_output_selection(options[1])
        else:
            self.output_selector.set("No outputs yet")
            self._on_output_selection("No outputs yet")

    def _display_csv(self, data: list):
        """Displays CSV data in a Treeview."""
        self._clear_dynamic_content()

        if not data:
            self.summary_text_display.grid(row=0, column=0, sticky="nsew")
            self.summary_text_display.delete("0.0", "end")
            self.summary_text_display.insert("0.0", "Rare Word List (CSV) not yet generated or is empty.")
            return

        if self.csv_treeview is None:
            style = ttk.Style()
            style.theme_use("default")
            style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", borderwidth=0)
            style.map('Treeview', background=[('selected', '#3470b6')])
            style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat")
            style.map("Treeview.Heading", background=[('active', '#6c757d')])

            headers = data[0] if data else []
            self.csv_treeview = ttk.Treeview(self.dynamic_content_frame, columns=headers, show="headings")
            for col in headers:
                self.csv_treeview.heading(col, text=col, anchor='w')
                self.csv_treeview.column(col, width=100, anchor='w') # Default width

            # Add scrollbar
            vsb = ttk.Scrollbar(self.dynamic_content_frame, orient="vertical", command=self.csv_treeview.yview)
            hsb = ttk.Scrollbar(self.dynamic_content_frame, orient="horizontal", command=self.csv_treeview.xview)
            self.csv_treeview.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            vsb.grid(row=0, column=1, sticky="ns")
            hsb.grid(row=1, column=0, sticky="ew")

        # Clear existing data
        self.csv_treeview.delete(*self.csv_treeview.get_children())

        # Populate with new data
        for row in data[1:]: # Skip headers
            self.csv_treeview.insert("", "end", values=row)

        self.csv_treeview.grid(row=0, column=0, sticky="nsew")

    def get_current_content_for_export(self):
        """Returns the currently displayed content for copy/save operations."""
        current_choice = self.output_selector.get()
        if current_choice == "Meta-Summary":
            return self._outputs.get("Meta-Summary", "")
        elif current_choice == "Rare Word List (CSV)":
            # Convert list of lists to CSV string
            data = self._outputs.get("Rare Word List (CSV)", [])
            if not data: return ""
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerows(data)
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
