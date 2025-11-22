"""
LocalScribe - Main Window (CustomTkinter Refactor)
"""
import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk, Menu
import os
import sys
import platform
import csv
from datetime import datetime
from pathlib import Path
from queue import Queue, Empty

from src.ui.widgets import FileReviewTable, ModelSelectionWidget, OutputOptionsWidget, DynamicOutputWidget
from src.ui.workers import ProcessingWorker
from src.cleaner import DocumentCleaner
from src.ai import ModelManager
from src.debug_logger import debug_log

# Helper function to create tooltips for CustomTkinter widgets
def create_tooltip(widget, text, position="right"):
    """
    Create a tooltip that appears on hover, positioned relative to the widget.
    Tooltip automatically disappears when mouse leaves the widget.

    Args:
        widget: The widget to attach the tooltip to
        text: The tooltip text to display
        position: "right" (default) or "left" - which side of the widget the tooltip appears
    """
    tooltip_window = None
    hide_timer = None

    def show_tooltip(event):
        nonlocal tooltip_window, hide_timer

        # Cancel any pending hide
        if hide_timer:
            widget.after_cancel(hide_timer)
            hide_timer = None

        # If tooltip already exists, don't create another
        if tooltip_window:
            return

        # Create tooltip window
        tooltip_window = ctk.CTkToplevel(widget)
        tooltip_window.wm_overrideredirect(True) # Remove window decorations
        tooltip_window.wm_attributes("-topmost", True)  # Keep on top

        label = ctk.CTkLabel(tooltip_window, text=text,
                             bg_color=("#333333", "#333333"), # Dark background
                             text_color=("white", "white"), # White text
                             corner_radius=5,
                             wraplength=200) # Wrap text after 200 pixels
        label.pack(padx=5, pady=5)

        # Get tooltip dimensions
        tooltip_window.update_idletasks()
        tooltip_width = tooltip_window.winfo_width()
        tooltip_height = tooltip_window.winfo_height()

        # Get widget position on screen
        widget_x = widget.winfo_rootx()
        widget_y = widget.winfo_rooty()
        widget_width = widget.winfo_width()
        widget_height = widget.winfo_height()

        # Get screen dimensions
        screen_width = widget.winfo_toplevel().winfo_screenwidth()

        # Position tooltip based on requested position and screen space
        if position == "left":
            # Position to the left of the widget with 10px gap
            x = widget_x - tooltip_width - 10
            # Ensure we don't go off the left edge
            if x < 0:
                x = widget_x + widget_width + 10  # Fall back to right side
        else:  # position == "right" (default)
            # Position to the right of the widget with 10px gap
            x = widget_x + widget_width + 10
            # Check if tooltip would go off the right edge
            if x + tooltip_width > screen_width:
                x = widget_x - tooltip_width - 10  # Show on left instead
                # If left side also doesn't work, squeeze it at the right edge
                if x < 0:
                    x = screen_width - tooltip_width - 10

        # Position vertically centered with the widget
        y = widget_y + (widget_height // 2) - (tooltip_height // 2)

        # Keep tooltip on screen vertically
        screen_height = widget.winfo_toplevel().winfo_screenheight()
        if y < 0:
            y = 0
        elif y + tooltip_height > screen_height:
            y = screen_height - tooltip_height

        tooltip_window.wm_geometry(f"+{x}+{y}")

    def hide_tooltip(event):
        nonlocal tooltip_window, hide_timer

        # Schedule hide with short delay to prevent flickering
        def do_hide():
            nonlocal tooltip_window
            if tooltip_window:
                try:
                    tooltip_window.destroy()
                except:
                    pass
                tooltip_window = None

        # Cancel any pending hide
        if hide_timer:
            widget.after_cancel(hide_timer)

        # Schedule hide for next event loop iteration
        hide_timer = widget.after(50, do_hide)

    # Bind to the widget (icon)
    widget.bind("<Enter>", show_tooltip)
    widget.bind("<Leave>", hide_tooltip)


class MainWindow(ctk.CTk):
    """
    Main application window for LocalScribe, refactored with CustomTkinter.
    """

    def __init__(self):
        super().__init__()
        self.title("LocalScribe - Legal Document Processor")
        self.geometry("1200x800")

        # State
        self.selected_files = []
        self.processing_results = []
        self.worker = None
        
        # AI Model Manager
        self.model_manager = ModelManager()

        # Threading Queue
        self.ui_queue = Queue()

        # Initialize UI
        self._create_main_layout()
        self._create_menus()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

        # Start queue polling
        self.after(100, self._process_queue)
        
        # Check Ollama service on startup
        self._check_ollama_service()
        # Refresh model selector after Ollama check
        self.model_selection.refresh_status()

    def _create_main_layout(self):
        """Creates the main grid layout."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _create_menus(self):
        """Create a native-style menubar using tkinter.Menu with dark theme colors."""
        # Dark grey colors to match CustomTkinter's palette
        # Using darker grey (#404040) instead of pure #2b2b2b for menu bar readability
        bg_color = "#404040"  # Dark grey background
        fg_color = "#ffffff"  # White text
        active_bg = "#505050" # Slightly lighter grey for hover
        active_fg = "#ffffff" # White text on hover

        self.menubar = Menu(self, bg=bg_color, fg=fg_color,
                           activebackground=active_bg, activeforeground=active_fg,
                           borderwidth=1, relief="flat",
                           disabledforeground="#666666")
        self.config(menu=self.menubar)

        file_menu = Menu(self.menubar, tearoff=0,
                        bg=bg_color, fg=fg_color,
                        activebackground=active_bg, activeforeground=active_fg,
                        borderwidth=0, relief="flat",
                        disabledforeground="#666666")
        self.menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Select Files...", command=self.select_files)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)

        help_menu = Menu(self.menubar, tearoff=0,
                        bg=bg_color, fg=fg_color,
                        activebackground=active_bg, activeforeground=active_fg,
                        borderwidth=0, relief="flat",
                        disabledforeground="#666666")
        self.menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

    def show_about(self):
        messagebox.showinfo("About LocalScribe", "LocalScribe v2.1\n\n100% Offline Legal Document Processor")

    def _create_toolbar(self):
        """Create toolbar with file selection controls."""
        self.toolbar_frame = ctk.CTkFrame(self, height=50, corner_radius=0)
        self.toolbar_frame.grid(row=0, column=0, sticky="ew")
        self.toolbar_frame.grid_columnconfigure(1, weight=1)

        self.select_files_btn = ctk.CTkButton(self.toolbar_frame, text="Select Files...", command=self.select_files)
        self.select_files_btn.grid(row=0, column=0, padx=10, pady=10)

        self.files_label = ctk.CTkLabel(self.toolbar_frame, text="No files selected", text_color="gray")
        self.files_label.grid(row=0, column=2, padx=10, pady=10)

    def _create_central_widget(self):
        """Create the four-quadrant central widget."""
        self.main_content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Configure a 2x2 grid
        self.main_content_frame.grid_columnconfigure(0, weight=1) # Left column
        self.main_content_frame.grid_columnconfigure(1, weight=1) # Right column
        self.main_content_frame.grid_rowconfigure(0, weight=1)    # Top row
        self.main_content_frame.grid_rowconfigure(1, weight=1)    # Bottom row

        # Create frames for each quadrant
        top_left_frame = ctk.CTkFrame(self.main_content_frame)
        top_right_frame = ctk.CTkFrame(self.main_content_frame)
        bottom_left_frame = ctk.CTkFrame(self.main_content_frame)
        bottom_right_frame = ctk.CTkFrame(self.main_content_frame)

        # Place frames in the grid
        top_left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=(0, 5))
        top_right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=(0, 5))
        bottom_left_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 5), pady=(5, 0))
        bottom_right_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 0), pady=(5, 0))

        # Configure quadrant frames to have a grid for internal layout and tooltip icon
        for frame in [top_left_frame, top_right_frame, bottom_left_frame, bottom_right_frame]:
            frame.grid_rowconfigure(0, weight=0) # For tooltip icon
            frame.grid_rowconfigure(1, weight=1) # For content
            frame.grid_columnconfigure(0, weight=1)

        # --- Populate Quadrants ---
        # NOTE: All quadrant headers follow a consistent style convention:
        # - Font size: 16pt, bold weight
        # - Alignment: centered within the quadrant
        # - Tooltip icon positioned on the right with help text
        # - Future headers should follow this same pattern for UI consistency

        # Top-Left: File Review Table and Tooltip
        files_label = ctk.CTkLabel(top_left_frame, text="Document Selection", font=ctk.CTkFont(size=16, weight="bold"))
        files_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5,0))
        files_label.configure(anchor="center")
        tooltip_icon_tl = ctk.CTkLabel(top_left_frame, text="📄", font=ctk.CTkFont(size=14))
        tooltip_icon_tl.grid(row=0, column=1, sticky="e", padx=5, pady=(5,0))
        create_tooltip(tooltip_icon_tl, "Select documents to process. The program distinguishes between digital PDFs (direct text extraction) and scanned PDFs (OCR required, which may introduce errors).")

        self.file_table = FileReviewTable(top_left_frame)
        self.file_table.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        # Top-Right: Model Selection and Tooltip
        model_label = ctk.CTkLabel(top_right_frame, text="AI Model Selection", font=ctk.CTkFont(size=16, weight="bold"))
        model_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5,0))
        model_label.configure(anchor="center")
        tooltip_icon_tr = ctk.CTkLabel(top_right_frame, text="🤖", font=ctk.CTkFont(size=14))
        tooltip_icon_tr.grid(row=0, column=1, sticky="e", padx=5, pady=(5,0))
        create_tooltip(tooltip_icon_tr, "Choose an AI model for summarization. Larger models may offer better quality but will take longer to process. All models run locally on your machine, ensuring privacy and PII safety.", position="left")

        self.model_selection = ModelSelectionWidget(top_right_frame, self.model_manager)
        self.model_selection.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # Bottom-Left: Dynamic Output Display and Tooltip
        output_display_label = ctk.CTkLabel(bottom_left_frame, text="Generated Outputs", font=ctk.CTkFont(size=16, weight="bold"))
        output_display_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5,0))
        output_display_label.configure(anchor="center")
        tooltip_icon_bl = ctk.CTkLabel(bottom_left_frame, text="📝", font=ctk.CTkFont(size=14))
        tooltip_icon_bl.grid(row=0, column=1, sticky="e", padx=5, pady=(5,0))
        create_tooltip(tooltip_icon_bl, "View generated outputs here. Summaries are AI-generated and can be imperfect, but hopefully still useful. Use the dropdown to switch between individual summaries, the meta-summary, or the rare word list CSV.")

        self.summary_results = DynamicOutputWidget(bottom_left_frame)
        self.summary_results.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)

        # Bottom-Right: Output Options and Tooltip
        output_options_label = ctk.CTkLabel(bottom_right_frame, text="Output Options", font=ctk.CTkFont(size=16, weight="bold"))
        output_options_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5,0))
        output_options_label.configure(anchor="center")
        tooltip_icon_br = ctk.CTkLabel(bottom_right_frame, text="⚙️", font=ctk.CTkFont(size=14))
        tooltip_icon_br.grid(row=0, column=1, sticky="e", padx=5, pady=(5,0))
        create_tooltip(tooltip_icon_br, "Configure desired outputs. Each selected output (individual summaries, meta-summary, rare word list) adds to the processing time. Only generate what you need.", position="left")
        
        self.output_options = OutputOptionsWidget(bottom_right_frame)
        self.output_options.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        
        self.generate_outputs_btn = ctk.CTkButton(bottom_right_frame, text="Generate All Outputs", command=self._start_generation)
        self.generate_outputs_btn.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)
        self.generate_outputs_btn.configure(state="disabled") # Disabled until files are selected

    def _create_status_bar(self):
        """Create status bar for messages."""
        self.status_bar_frame = ctk.CTkFrame(self, height=25, corner_radius=0)
        self.status_bar_frame.grid(row=2, column=0, sticky="ew")
        self.status_label = ctk.CTkLabel(self.status_bar_frame, text="Ready", anchor="w")
        self.status_label.pack(side="left", padx=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.status_bar_frame, mode="determinate")
        self.progress_bar.set(0)
        
    def select_files(self):
        """Open file dialog and update selected files."""
        filepaths = filedialog.askopenfilenames(
            title="Select Legal Documents",
            filetypes=(("Documents", "*.pdf *.txt *.rtf"), ("All files", "*.*"))
        )
        if filepaths:
            self.selected_files = filepaths
            self.files_label.configure(text=f"{len(filepaths)} file(s) selected")
            self.generate_outputs_btn.configure(state="normal")
            
            # Populate file table with initial pending status
            self.file_table.clear() # Clear existing entries
            for filepath in filepaths:
                filename = os.path.basename(filepath)
                file_size = os.path.getsize(filepath) # Get actual file size
                self.file_table.add_result({
                    'filename': filename,
                    'status': 'pending',
                    'method': 'N/A',
                    'confidence': 0,
                    'page_count': 0, # Page count requires processing, keep as 0 for now
                    'file_size': file_size
                })

        else:
            self.selected_files = []
            self.files_label.configure(text="No files selected")
            self.generate_outputs_btn.configure(state="disabled")
            self.file_table.clear()

    def _start_generation(self):
        """Initiate the processing and generation of outputs."""
        if not self.selected_files:
            messagebox.showwarning("No Files Selected", "Please select documents to process first.")
            return
        
        # Get selected model and summary length
        selected_model = self.model_selection.model_selector.get()
        if selected_model == "Loading..." or selected_model == "Ollama not found":
            messagebox.showwarning("Model Not Selected", "Please select a valid AI model.")
            return

        summary_length = int(self.output_options.length_slider.get())

        # Get output options
        output_options = {
            "individual_summaries": self.output_options.individual_summaries_check.get(),
            "meta_summary": self.output_options.meta_summary_check.get(),
            "vocab_csv": self.output_options.vocab_csv_check.get()
        }

        # Check if at least one output option is selected
        if not any(output_options.values()):
            messagebox.showwarning("No Output Selected", "Please select at least one output type (Individual Summaries, Meta-Summary, or Rare Word List).")
            return

        self.start_processing(self.selected_files, selected_model, summary_length, output_options)

    def start_processing(self, file_paths, selected_model, summary_length, output_options):
        """Start background processing of selected documents."""
        self.select_files_btn.configure(state="disabled")
        self.generate_outputs_btn.configure(state="disabled") # Disable new button
        self.progress_bar.pack(side="right", padx=10, pady=5, fill="x", expand=True)
        # DO NOT clear the file table - users need to see which files are being processed
        # The table entries will be updated with status as files are processed
        self.processing_results = []
        self.summary_results.update_outputs(meta_summary="", vocab_csv_data=[], document_summaries={}) # Clear previous results

        self.worker = ProcessingWorker(
            file_paths, 
            self.ui_queue, 
            self.model_manager, 
            selected_model, 
            summary_length, 
            output_options
        )
        self.worker.start()

    def _process_queue(self):
        """Process messages from the worker thread queue."""
        try:
            while True:
                message_type, data = self.ui_queue.get_nowait()

                if message_type == 'progress':
                    percentage, message = data
                    self.progress_bar.set(percentage / 100.0)
                    self.status_label.configure(text=message)
                
                elif message_type == 'file_processed':
                    self.processing_results.append(data)
                    self.file_table.add_result(data)
                    if data.get('summary'): # Individual document summary
                        self.summary_results.update_outputs(document_summaries={data['filename']: data['summary']})

                elif message_type == 'meta_summary_generated':
                    self.summary_results.update_outputs(meta_summary=data)
                
                elif message_type == 'vocab_csv_generated':
                    self.summary_results.update_outputs(vocab_csv_data=data)

                elif message_type == 'finished':
                    self.select_files_btn.configure(state="normal")
                    self.generate_outputs_btn.configure(state="normal") # Re-enable new button
                    self.progress_bar.pack_forget()
                    self.status_label.configure(text="Processing complete.")
                
                elif message_type == 'error':
                    messagebox.showerror("Processing Error", data)
                    self.select_files_btn.configure(state="normal")
                    self.generate_outputs_btn.configure(state="normal") # Re-enable new button
                    self.progress_bar.pack_forget()

        except Empty:
            pass # No messages in queue
        finally:
            self.after(100, self._process_queue) # Poll again after 100ms

    def _check_ollama_service(self):
        """Check if Ollama service is running on startup."""
        try:
            self.model_manager.health_check()
            debug_log("[MAIN WINDOW] [OK] Ollama service is accessible on startup")
            self.status_label.configure(text="Ollama service connected.", text_color="green")
        except Exception as e:
            debug_log(f"[MAIN WINDOW] [ERROR] Ollama service not accessible: {str(e)}")
            self.status_label.configure(text="Ollama service not found!", text_color="red")
            messagebox.showwarning(
                "Ollama Service Not Found",
                "Ollama service is not accessible. Please ensure Ollama is running to generate summaries."
            )