"""
LocalScribe - Custom UI Widgets

This module contains reusable CustomTkinter widget components for the main application:
- FileReviewTable: Displays document processing results in a table format
- ModelSelectionWidget: AI model selection dropdown with Ollama integration
- OutputOptionsWidget: Configuration controls for summary length and output types

Note: System monitoring is handled by src/ui/system_monitor.py (not in this module).
"""
import customtkinter as ctk
from tkinter import ttk

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
    """Widget for selecting the AI model and prompt style."""
    def __init__(self, master, model_manager, prompt_template_manager=None, **kwargs):
        super().__init__(master, **kwargs)
        self.model_manager = model_manager
        self.prompt_template_manager = prompt_template_manager
        self._presets_cache = {}  # Maps display_name -> preset_id

        self.grid_columnconfigure(0, weight=1)

        # Model Selection
        model_label = ctk.CTkLabel(self, text="Model Selection (Ollama)", font=ctk.CTkFont(weight="bold"))
        model_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        self.model_selector = ctk.CTkComboBox(self, values=["Loading..."], command=self._on_model_changed)
        self.model_selector.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.local_model_info_label = ctk.CTkLabel(self, text="Models run locally and offline.", text_color="gray", font=ctk.CTkFont(size=11))
        self.local_model_info_label.grid(row=2, column=0, padx=10, pady=(0, 5), sticky="w")

        # Prompt Style Selection
        prompt_label = ctk.CTkLabel(self, text="Prompt Style", font=ctk.CTkFont(weight="bold"))
        prompt_label.grid(row=3, column=0, padx=10, pady=(5, 0), sticky="w")

        self.prompt_selector = ctk.CTkComboBox(self, values=["Loading..."])
        self.prompt_selector.grid(row=4, column=0, padx=10, pady=5, sticky="ew")

        # Tooltip for prompt selector - will be set with actual path after refresh_prompts()
        self._prompt_tooltip_text = "Choose summarization style."
        self._user_prompts_path = None  # Will be set by refresh_prompts()

        self.prompt_info_label = ctk.CTkLabel(
            self,
            text="See _README.txt in prompts folder for custom prompt guide.",
            text_color="gray",
            font=ctk.CTkFont(size=11)
        )
        self.prompt_info_label.grid(row=5, column=0, padx=10, pady=(0, 10), sticky="w")

    def _on_model_changed(self, model_name=None):
        """Called when model selection changes - refresh both model status and prompts."""
        self.refresh_status(model_name)
        self.refresh_prompts()

    def refresh_status(self, model_name=None):
        """Refresh the available models list."""
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

    def refresh_prompts(self, model_name: str = "phi-3-mini"):
        """
        Refresh the available prompt presets for the current model.

        Args:
            model_name: Model name to get prompts for (default: phi-3-mini for templates)
        """
        if not self.prompt_template_manager:
            self.prompt_selector.configure(values=["Factual Summary"])
            self.prompt_selector.set("Factual Summary")
            return

        # Ensure skeleton template exists for user
        self.prompt_template_manager.ensure_user_skeleton(model_name)

        # Get available presets
        presets = self.prompt_template_manager.get_available_presets(model_name)

        if not presets:
            self.prompt_selector.configure(values=["Factual Summary"])
            self.prompt_selector.set("Factual Summary")
            return

        # Build display names and cache mapping
        self._presets_cache.clear()
        display_names = []
        default_selection = None

        for preset in presets:
            display_name = preset['name']
            # All prompts appear equally in dropdown (no special suffix)
            display_names.append(display_name)
            self._presets_cache[display_name] = preset['id']

            # Default to "Factual Summary" if available
            if preset['id'] == 'factual-summary':
                default_selection = display_name

        self.prompt_selector.configure(values=display_names)

        # Set default selection
        if default_selection:
            self.prompt_selector.set(default_selection)
        elif display_names:
            self.prompt_selector.set(display_names[0])

        # Update tooltip with user prompts path
        user_path = self.prompt_template_manager.get_user_prompts_path(model_name)
        if user_path:
            self._prompt_tooltip_text = f"Choose summarization style.\nAdd custom prompts to:\n{user_path}"

    def get_selected_preset_id(self) -> str:
        """
        Get the preset ID for the currently selected prompt style.

        Returns:
            Preset ID string (e.g., 'factual-summary')
        """
        display_name = self.prompt_selector.get()
        return self._presets_cache.get(display_name, 'factual-summary')

    def setup_tooltip(self, create_tooltip_func):
        """
        Set up tooltip for the prompt selector.

        Args:
            create_tooltip_func: The create_tooltip function from tooltip_helper
        """
        create_tooltip_func(self.prompt_selector, self._prompt_tooltip_text)

class OutputOptionsWidget(ctk.CTkFrame):
    """Widget for configuring desired outputs."""
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_columnconfigure(0, weight=1)

        # Reference to generate button (set by quadrant_builder after creation)
        self._generate_btn = None

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

        self.individual_summaries_check = ctk.CTkCheckBox(
            self, text="Individual Summaries",
            command=self._update_generate_button_text
        )
        self.individual_summaries_check.grid(row=4, column=0, padx=10, pady=5, sticky="w")
        self.individual_summaries_check.deselect() # Off by default

        self.meta_summary_check = ctk.CTkCheckBox(
            self, text="Meta-Summary of All Documents",
            command=self._update_generate_button_text
        )
        self.meta_summary_check.grid(row=5, column=0, padx=10, pady=5, sticky="w")
        self.meta_summary_check.select() # On by default

        self.vocab_csv_check = ctk.CTkCheckBox(
            self, text="Rare Word List (CSV)",
            command=self._update_generate_button_text
        )
        self.vocab_csv_check.grid(row=6, column=0, padx=10, pady=5, sticky="w")
        self.vocab_csv_check.select()  # On by default

    def set_generate_button(self, button):
        """
        Set reference to the generate button for dynamic text updates.

        Args:
            button: The CTkButton to update
        """
        self._generate_btn = button
        self._update_generate_button_text()

    def set_document_count(self, count: int):
        """
        Set the number of documents selected for processing.
        Used to calculate output count when individual summaries is checked.

        Args:
            count: Number of documents selected
        """
        self._document_count = count
        self._update_generate_button_text()

    def _update_generate_button_text(self):
        """Update generate button text based on number of outputs to generate."""
        if self._generate_btn is None:
            return

        count = self.get_output_count()
        if count == 0:
            self._generate_btn.configure(text="Select Outputs")
        elif count == 1:
            self._generate_btn.configure(text="Generate 1 Output")
        else:
            self._generate_btn.configure(text=f"Generate {count} Outputs")

    def get_output_count(self) -> int:
        """
        Return the total number of outputs that will be generated.

        Individual summaries count = number of documents (not 1).
        Meta-summary and vocab CSV each count as 1.
        """
        count = 0
        doc_count = getattr(self, '_document_count', 0)

        if self.individual_summaries_check.get():
            # Individual summaries = one per document
            count += max(doc_count, 1)  # At least 1 if checkbox is checked
        if self.meta_summary_check.get():
            count += 1
        if self.vocab_csv_check.get():
            count += 1
        return count

    def get_checked_count(self) -> int:
        """Return the number of checked checkboxes (not document-aware)."""
        count = 0
        if self.individual_summaries_check.get():
            count += 1
        if self.meta_summary_check.get():
            count += 1
        if self.vocab_csv_check.get():
            count += 1
        return count

    def lock_controls(self):
        """Disable all output option controls during processing."""
        self.length_slider.configure(state="disabled")
        self.individual_summaries_check.configure(state="disabled")
        self.meta_summary_check.configure(state="disabled")
        self.vocab_csv_check.configure(state="disabled")

    def unlock_controls(self):
        """Re-enable all output option controls after processing completes."""
        self.length_slider.configure(state="normal")
        self.individual_summaries_check.configure(state="normal")
        self.meta_summary_check.configure(state="normal")
        self.vocab_csv_check.configure(state="normal")

