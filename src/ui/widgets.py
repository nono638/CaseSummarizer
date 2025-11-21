"""
LocalScribe - Custom UI Widgets (CustomTkinter Refactor)
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
import os

# Import prompt configuration
from ..prompt_config import get_prompt_config

class FileReviewTable(ctk.CTkFrame):
    """
    Custom table widget for displaying document processing results,
    refactored with CustomTkinter using a tkinter.ttk.Treeview.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.column_map = {
            "include": ("Include", 50),
            "filename": ("Filename", 300),
            "status": ("Status", 100),
            "method": ("Method", 100),
            "confidence": ("Confidence", 100),
            "pages": ("Pages", 50),
            "size": ("Size", 80)
        }
        
        self._create_treeview()
        
    def _create_treeview(self):
        """Create the Treeview widget."""
        style = ttk.Style()
        style.theme_use("default")
        
        # Configure Treeview colors to match CustomTkinter theme
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        fieldbackground="#2b2b2b", 
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#3470b6')])
        
        style.configure("Treeview.Heading", 
                        background="#565b5e", 
                        foreground="white", 
                        relief="flat")
        style.map("Treeview.Heading", background=[('active', '#6c757d')])

        self.tree = ttk.Treeview(self, 
                                 columns=list(self.column_map.keys()), 
                                 show="headings")
        
        for col_id, (text, width) in self.column_map.items():
            self.tree.heading(col_id, text=text, anchor='w')
            self.tree.column(col_id, width=width, anchor='w')

        self.tree.pack(expand=True, fill="both")

    def add_result(self, result):
        """Add a processing result to the table."""
        filename = result.get('filename', 'Unknown')
        status = result.get('status', 'error')
        confidence = result.get('confidence', 0)
        
        status_text, status_color_tag = self._get_status_display(status, confidence)
        method_display = self._get_method_display(result.get('method', 'unknown'))
        confidence_display = f"{confidence}%" if status != 'error' else "—"
        pages_display = str(result.get('page_count', 0)) or "—"
        size_display = self._format_file_size(result.get('file_size', 0)) if status != 'error' else "—"

        # Using a placeholder for the "Include" checkbox for now
        include_display = "✓" if status == 'success' and confidence >= 70 else " "

        values = (
            include_display,
            filename,
            status_text,
            method_display,
            confidence_display,
            pages_display,
            size_display
        )
        self.tree.insert("", "end", values=values, tags=(status_color_tag,))

        # Configure colors for tags
        self.tree.tag_configure('green', foreground='#28a745')
        self.tree.tag_configure('yellow', foreground='#ffc107')
        self.tree.tag_configure('red', foreground='#dc3545')

    def _get_status_display(self, status, confidence):
        if status == 'error': return ("✗ Failed", "red")
        if status == 'success' and confidence >= 70: return ("✓ Ready", "green")
        return ("⚠ Low Quality", "yellow")

    def _get_method_display(self, method):
        return method.replace('_', ' ').title()

    def _format_file_size(self, size_bytes):
        if size_bytes == 0: return "0 B"
        units = ['B', 'KB', 'MB', 'GB']
        size = float(size_bytes)
        unit_index = 0
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        return f"{size:.1f} {units[unit_index]}"

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

class AIControlsWidget(ctk.CTkFrame):
    """AI Controls panel refactored for CustomTkinter."""

    def __init__(self, master, model_manager, **kwargs):
        super().__init__(master, **kwargs)
        self.model_manager = model_manager
        
        self.grid_columnconfigure(0, weight=1)
        
        # Model Selection
        model_label = ctk.CTkLabel(self, text="Model Selection (Ollama)", font=ctk.CTkFont(weight="bold"))
        model_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")
        
        self.model_selector = ctk.CTkComboBox(self, values=["Loading..."], command=self.refresh_status)
        self.model_selector.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        # Summary Length
        length_label = ctk.CTkLabel(self, text="Summary Length (Approx)", font=ctk.CTkFont(weight="bold"))
        length_label.grid(row=2, column=0, padx=10, pady=(10, 0), sticky="w")

        self.length_slider = ctk.CTkSlider(self, from_=100, to=500, number_of_steps=40)
        self.length_slider.set(200)
        self.length_slider.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        
        self.length_value_label = ctk.CTkLabel(self, text=f"{self.length_slider.get():.0f} words")
        self.length_slider.configure(command=lambda v: self.length_value_label.configure(text=f"{v:.0f} words"))
        self.length_value_label.grid(row=4, column=0, padx=10, pady=(0, 10), sticky="w")

    def refresh_status(self, model_name=None):
        try:
            available_models = self.model_manager.get_available_models()
            self.model_selector.configure(values=available_models)
            if available_models:
                self.model_selector.set(available_models[0])
        except Exception as e:
            self.model_selector.configure(values=["Ollama not found"])
            self.model_selector.set("Ollama not found")

class SummaryResultsWidget(ctk.CTkFrame):
    """Widget to display AI-generated summary, refactored for CustomTkinter."""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Stats bar
        self.stats_frame = ctk.CTkFrame(self)
        self.stats_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.word_count_label = ctk.CTkLabel(self.stats_frame, text="Words: 0")
        self.word_count_label.pack(side="left", padx=10)

        # Summary text box
        self.summary_text = ctk.CTkTextbox(self, wrap="word")
        self.summary_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=0)
        self.summary_text.insert("0.0", "Generated summary will appear here...")

        # Button bar
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
        
        self.copy_btn = ctk.CTkButton(self.button_frame, text="Copy to Clipboard", command=self.copy_to_clipboard)
        self.copy_btn.pack(side="left", padx=5)

        self.save_btn = ctk.CTkButton(self.button_frame, text="Save to File...", command=self.save_to_file)
        self.save_btn.pack(side="left", padx=5)

    def copy_to_clipboard(self):
        summary = self.summary_text.get("0.0", "end")
        self.clipboard_clear()
        self.clipboard_append(summary)
        messagebox.showinfo("Copied", "Summary copied to clipboard.")

    def save_to_file(self):
        summary = self.summary_text.get("0.0", "end")
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Save Summary"
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(summary)
            messagebox.showinfo("Saved", f"Summary saved to {filepath}")