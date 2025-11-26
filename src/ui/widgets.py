"""
LocalScribe - Custom UI Widgets (CustomTkinter Refactor)
"""
import customtkinter as ctk
from tkinter import ttk, messagebox
import os
import psutil # For CPU/GPU monitoring

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
        self.file_item_map = {} # To map filename to treeview item ID

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
        """Add or update a processing result in the table."""
        filename = result.get('filename', 'Unknown')
        
        values, status_color_tag = self._prepare_result_for_display(result)

        if filename in self.file_item_map:
            # Update existing item
            item_id = self.file_item_map[filename]
            self.tree.item(item_id, values=values, tags=(status_color_tag,))
        else:
            # Insert new item
            item_id = self.tree.insert("", "end", values=values, tags=(status_color_tag,))
            self.file_item_map[filename] = item_id

        # Configure colors for tags
        self.tree.tag_configure('green', foreground='#28a745')
        self.tree.tag_configure('yellow', foreground='#ffc107')
        self.tree.tag_configure('red', foreground='#dc3545')
        self.tree.tag_configure('pending', foreground='gray')


    def _prepare_result_for_display(self, result):
        """Prepares result data for display in the treeview."""
        status = result.get('status', 'error')
        confidence = result.get('confidence', 0)
        
        status_text, status_color_tag = self._get_status_display(status, confidence)
        method_display = self._get_method_display(result.get('method', 'unknown'))
        confidence_display = f"{confidence}%" if status != 'error' and confidence > 0 else "—"
        pages_display = str(result.get('page_count', 0)) if result.get('page_count') else "—"
        size_display = self._format_file_size(result.get('file_size', 0)) if status != 'error' else "—"

        # Using a placeholder for the "Include" checkbox for now
        include_display = "✓" if status == 'success' and confidence >= 70 else " "
        
        values = (
            include_display,
            result.get('filename', 'Unknown'),
            status_text,
            method_display,
            confidence_display,
            pages_display,
            size_display
        )
        return values, status_color_tag

    def _get_status_display(self, status, confidence):
        if status == 'error': return ("✗ Failed", "red")
        if status == 'pending': return ("... Pending", "pending")
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
        
        # Round to nearest integer for all units
        return f"{round(size)} {units[unit_index]}"

    def clear(self):
        self.file_item_map.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

class ModelSelectionWidget(ctk.CTkFrame):
    """Widget for selecting the AI model."""
    def __init__(self, master, model_manager, **kwargs):
        super().__init__(master, **kwargs)
        self.model_manager = model_manager

        self.grid_columnconfigure(0, weight=1)

        model_label = ctk.CTkLabel(self, text="Model Selection (Ollama)", font=ctk.CTkFont(weight="bold"))
        model_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        self.model_selector = ctk.CTkComboBox(self, values=["Loading..."], command=self.refresh_status)
        self.model_selector.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        
        self.local_model_info_label = ctk.CTkLabel(self, text="Models run locally and offline.", text_color="gray", font=ctk.CTkFont(size=11))
        self.local_model_info_label.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")

    def refresh_status(self, model_name=None):
        try:
            available_models_dict = self.model_manager.get_available_models()
            available_model_names = list(available_models_dict.keys())

            self.model_selector.configure(values=available_model_names)

            # If user selected a model (model_name provided), use it
            # Otherwise, keep current selection or use first model
            if model_name and model_name in available_model_names:
                self.model_selector.set(model_name)
            elif available_model_names:
                # Only set to first model if current selection is invalid
                current = self.model_selector.get()
                if current not in available_model_names:
                    self.model_selector.set(available_model_names[0])
            else:
                self.model_selector.set("No models found")
        except Exception as e:
            self.model_selector.configure(values=["Ollama not found"])
            self.model_selector.set("Ollama not found")

class OutputOptionsWidget(ctk.CTkFrame):
    """Widget for configuring desired outputs."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        # Summary Length
        length_label = ctk.CTkLabel(self, text="Summary Length (Approx)", font=ctk.CTkFont(weight="bold"))
        length_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        self.length_slider = ctk.CTkSlider(self, from_=100, to=500, number_of_steps=40)
        self.length_slider.set(200)
        self.length_slider.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.length_value_label = ctk.CTkLabel(self, text=f"{self.length_slider.get():.0f} words")
        self.length_slider.configure(command=lambda v: self.length_value_label.configure(text=f"{v:.0f} words"))
        self.length_value_label.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")

        # Output Type Checkboxes
        output_type_label = ctk.CTkLabel(self, text="Desired Outputs", font=ctk.CTkFont(weight="bold"))
        output_type_label.grid(row=3, column=0, padx=10, pady=(10, 0), sticky="w")

        self.individual_summaries_check = ctk.CTkCheckBox(self, text="Individual Summaries")
        self.individual_summaries_check.grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.individual_summaries_check.deselect() # Off by default

        self.meta_summary_check = ctk.CTkCheckBox(self, text="Meta-Summary of All Documents")
        self.meta_summary_check.grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.meta_summary_check.select() # On by default

        self.vocab_csv_check = ctk.CTkCheckBox(self, text="Rare Word List (CSV)")
        self.vocab_csv_check.grid(row=6, column=0, padx=10, pady=5, sticky="w")
        self.vocab_csv_check.select() # On by default


class SystemMonitorWidget(ctk.CTkFrame):
    """Widget to display system resource usage (CPU/GPU)."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.cpu_label = ctk.CTkLabel(self, text="CPU: 0%", font=ctk.CTkFont(size=12))
        self.cpu_label.grid(row=0, column=0, padx=5, pady=2, sticky="w")

        self.gpu_label = ctk.CTkLabel(self, text="GPU: N/A", font=ctk.CTkFont(size=12))
        self.gpu_label.grid(row=0, column=1, padx=5, pady=2, sticky="w")

        self.update_stats()

    def update_stats(self):
        """Update CPU and GPU usage stats."""
        # CPU Usage
        cpu_percent = psutil.cpu_percent(interval=None)
        self.cpu_label.configure(text=f"CPU: {cpu_percent:.1f}%")
        
        # NOTE: Getting GPU usage is platform-specific and complex.
        # This is a placeholder for now. A library like 'py-nvml' for NVIDIA
        # or platform-specific commands would be needed for a real implementation.
        self.gpu_label.configure(text="GPU: N/A")

        self.after(2000, self.update_stats) # Update every 2 seconds


