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
from src.ui.workers import ProcessingWorker, OllamaAIWorkerManager
from src.ui.dialogs import SettingsDialog
from src.ui.system_monitor import SystemMonitor
from src.cleaner import DocumentCleaner
from src.ai import ModelManager
from src.debug_logger import debug_log
from src.user_preferences import get_user_preferences

# Helper function to create tooltips for CustomTkinter widgets
def create_tooltip(widget, text, position="right"):
    """
    Create a stable tooltip that appears on hover without flickering.
    Uses delayed display and proper positioning to prevent enter/leave loops.

    Args:
        widget: The widget to attach the tooltip to
        text: The tooltip text to display
        position: "right" (default) or "left" - which side of the widget the tooltip appears
    """
    tooltip_window = None
    show_timer = None

    def schedule_show():
        """Schedule tooltip to appear after delay (prevents flickering)."""
        nonlocal show_timer
        cancel_show()  # Cancel any existing scheduled show
        show_timer = widget.after(500, show_tooltip_delayed)  # 500ms delay

    def cancel_show():
        """Cancel scheduled tooltip display."""
        nonlocal show_timer
        if show_timer:
            widget.after_cancel(show_timer)
            show_timer = None

    def show_tooltip_delayed():
        """Display tooltip (called after delay)."""
        nonlocal tooltip_window, show_timer
        show_timer = None

        # If tooltip already exists, don't create another
        if tooltip_window:
            return

        # Force widget geometry update before querying position
        widget.update_idletasks()

        # Create tooltip window using toplevel parent for proper hierarchy
        tooltip_window = ctk.CTkToplevel(widget.winfo_toplevel())
        tooltip_window.wm_overrideredirect(True)  # Remove window decorations
        tooltip_window.wm_attributes("-topmost", True)  # Keep on top
        tooltip_window.wm_attributes("-toolwindow", True)  # Prevent taskbar appearance on Windows

        label = ctk.CTkLabel(tooltip_window, text=text,
                             bg_color=("#333333", "#333333"),  # Dark background
                             text_color=("white", "white"),  # White text
                             corner_radius=5,
                             wraplength=200)  # Wrap text after 200 pixels
        label.pack(padx=5, pady=5)

        # Force tooltip to calculate its size (use update_idletasks for reliable sizing)
        tooltip_window.update_idletasks()
        tooltip_width = tooltip_window.winfo_width()
        tooltip_height = tooltip_window.winfo_height()

        # Get widget position on screen (after widget geometry is finalized)
        widget_x = widget.winfo_rootx()
        widget_y = widget.winfo_rooty()
        widget_width = widget.winfo_width()
        widget_height = widget.winfo_height()

        # Get screen dimensions
        screen_width = widget.winfo_screenwidth()
        screen_height = widget.winfo_screenheight()

        # Position tooltip with cascading fallback logic
        if position == "left":
            # Try left side first
            x = widget_x - tooltip_width - 15
        else:  # position == "right" (default)
            # Try right side first
            x = widget_x + widget_width + 15

        # Check boundaries and apply cascading fallback
        if x + tooltip_width > screen_width:
            # Right position would go off-screen, try left
            x = widget_x - tooltip_width - 15

        if x < 0:
            # Left position would go off-screen, clamp to screen edge
            x = max(0, min(widget_x, screen_width - tooltip_width - 10))

        # Position vertically centered with the widget, with bounds checking
        y = widget_y + (widget_height // 2) - (tooltip_height // 2)
        y = max(0, min(y, screen_height - tooltip_height))

        tooltip_window.wm_geometry(f"+{x}+{y}")

        # Ensure tooltip appears and is on top
        tooltip_window.lift()
        tooltip_window.update_idletasks()

    def hide_tooltip(event):
        """Hide tooltip immediately (no delay)."""
        nonlocal tooltip_window
        cancel_show()  # Cancel any pending show
        if tooltip_window:
            try:
                tooltip_window.destroy()
            except (RuntimeError, AttributeError):
                # RuntimeError: window already destroyed; AttributeError: invalid state
                pass
            tooltip_window = None

    def on_enter(event):
        """Handle mouse entering widget - schedule tooltip display."""
        schedule_show()

    def on_leave(event):
        """Handle mouse leaving widget - hide tooltip immediately."""
        hide_tooltip(event)

    # Bind to the widget (icon)
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


class MainWindow(ctk.CTk):
    """
    Main application window for LocalScribe, refactored with CustomTkinter.
    """

    def __init__(self):
        super().__init__()
        self.title("LocalScribe v2.1 - 100% Offline Legal Document Processor")
        self.geometry("1200x800")

        # State
        self.selected_files = []
        self.processing_results = []
        self.worker = None
        self.pending_ai_generation = None

        # AI Model Manager
        self.model_manager = ModelManager()

        # Threading Queue
        self.ui_queue = Queue()

        # AI Worker Manager for Ollama summaries
        self.ai_worker_manager = OllamaAIWorkerManager(self.ui_queue)

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
        # Darker colors to blend seamlessly with CustomTkinter dark theme
        bg_color = "#212121"   # Very dark (blends with UI)
        fg_color = "#ffffff"   # White text
        active_bg = "#333333"  # Slightly lighter for hover
        active_fg = "#ffffff"  # White text on hover

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
        file_menu.add_command(label="Select Files...", command=self.select_files, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Settings", command=self.show_settings, accelerator="Ctrl+,")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit, accelerator="Ctrl+Q")

        help_menu = Menu(self.menubar, tearoff=0,
                        bg=bg_color, fg=fg_color,
                        activebackground=active_bg, activeforeground=active_fg,
                        borderwidth=0, relief="flat",
                        disabledforeground="#666666")
        self.menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About LocalScribe v2.1", command=self.show_about)

        # Bind keyboard shortcuts
        self.bind("<Control-o>", lambda e: self.select_files())
        self.bind("<Control-comma>", lambda e: self.show_settings())
        self.bind("<Control-q>", lambda e: self.quit())

    def show_about(self):
        messagebox.showinfo("About LocalScribe", "LocalScribe v2.1\n\n100% Offline Legal Document Processor")

    def show_settings(self):
        """Open the Settings dialog."""
        prefs = get_user_preferences()
        current_fraction = prefs.get_cpu_fraction()

        def on_save(cpu_fraction):
            """Callback when user saves settings."""
            prefs.set_cpu_fraction(cpu_fraction)
            messagebox.showinfo("Settings Saved", f"CPU allocation set to {int(cpu_fraction * 100)}%")

        dialog = SettingsDialog(self, current_fraction, on_save_callback=on_save)
        self.wait_window(dialog)  # Wait for dialog to close

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

        # Configure quadrant frames with borders and internal layout
        # Row 0: Header with emoji inline
        # Row 1+: Content widgets
        for frame in [top_left_frame, top_right_frame, bottom_left_frame, bottom_right_frame]:
            frame.grid_rowconfigure(0, weight=0)  # Header row
            frame.grid_rowconfigure(1, weight=1)  # Content row
            frame.grid_columnconfigure(0, weight=1)
            # Add subtle border
            frame.configure(border_width=1, border_color="#404040")

        # --- Populate Quadrants ---
        # NOTE: Headers now have emojis inline: "📄 Document Selection"
        # This prevents cutoff and provides better space utilization

        # Top-Left: File Review Table
        files_label = ctk.CTkLabel(
            top_left_frame,
            text="📄 Document Selection",
            font=ctk.CTkFont(size=17, weight="bold")
        )
        files_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8))

        create_tooltip(
            files_label,
            "Digital PDF: Text extracted directly. Scanned PDF: Uses Tesseract OCR (confidence-weighted cleaning, may introduce errors). TXT/RTF: Direct text extraction.\n\n"
            "Batch: Up to 100 docs. ProcessingTime ≈ (avg_pages × model_size). Supports .pdf, .txt, .rtf.",
            position="right"
        )

        self.file_table = FileReviewTable(top_left_frame)
        self.file_table.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Top-Right: Model Selection
        model_label = ctk.CTkLabel(
            top_right_frame,
            text="🤖 AI Model Selection",
            font=ctk.CTkFont(size=17, weight="bold")
        )
        model_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8))

        create_tooltip(
            model_label,
            "Any Ollama model supported. LocalScribe auto-detects & applies model-specific instruction formats ([INST] for Llama/Mistral, raw for Gemma, etc.).\n\n"
            "Size guidance: 1B=fast/basic, 7B=quality, 13B=best (slower). Larger = better reasoning. See Phase 2.7 for format compatibility.",
            position="right"
        )

        self.model_selection = ModelSelectionWidget(top_right_frame, self.model_manager)
        self.model_selection.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Bottom-Left: Dynamic Output Display
        output_display_label = ctk.CTkLabel(
            bottom_left_frame,
            text="📝 Generated Outputs",
            font=ctk.CTkFont(size=17, weight="bold")
        )
        output_display_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8))

        create_tooltip(
            output_display_label,
            "Individual summaries: Per-document outputs (from parallel processing). Meta-summary: Hierarchical summary of all docs (blocking final step). "
            "Vocabulary: CSV of technical terms (category, definition, relevance). Dropdown switches between output types. Copy/Save buttons available.",
            position="right"
        )

        self.summary_results = DynamicOutputWidget(bottom_left_frame)
        self.summary_results.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        # Bottom-Right: Output Options
        output_options_label = ctk.CTkLabel(
            bottom_right_frame,
            text="⚙️ Output Options",
            font=ctk.CTkFont(size=17, weight="bold")
        )
        output_options_label.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 8))

        create_tooltip(
            output_options_label,
            "Word count: 50-500 words per summary (adjusts token budget). Outputs: Toggle which results to generate (save time by disabling unneeded outputs). "
            "Parallel processing uses CPU fraction from Settings. Monitor system impact via status bar CPU/RAM display.",
            position="right"
        )

        self.output_options = OutputOptionsWidget(bottom_right_frame)
        self.output_options.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.generate_outputs_btn = ctk.CTkButton(
            bottom_right_frame,
            text="Generate All Outputs",
            command=self._start_generation,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.generate_outputs_btn.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        self.generate_outputs_btn.configure(state="disabled")

    def _create_status_bar(self):
        """Create status bar for messages and system monitoring."""
        self.status_bar_frame = ctk.CTkFrame(self, height=25, corner_radius=0)
        self.status_bar_frame.grid(row=2, column=0, sticky="ew")
        self.status_bar_frame.grid_columnconfigure(0, weight=1)  # Status label expands
        self.status_bar_frame.grid_columnconfigure(1, weight=0)  # Progress bar fixed
        self.status_bar_frame.grid_columnconfigure(2, weight=0)  # Monitor fixed

        self.status_label = ctk.CTkLabel(self.status_bar_frame, text="Ready", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="ew", padx=10)

        self.progress_bar = ctk.CTkProgressBar(self.status_bar_frame, mode="determinate")
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=1, sticky="e", padx=(5, 5))

        # Add system monitor (CPU/RAM display with hover tooltip)
        self.system_monitor = SystemMonitor(self.status_bar_frame)
        self.system_monitor.grid(row=0, column=2, sticky="e", padx=(0, 5))
        
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

        # Store AI generation parameters for after document cleaning completes
        self.pending_ai_generation = {
            "selected_model": selected_model,
            "summary_length": summary_length,
            "output_options": output_options
        }

        self.worker = ProcessingWorker(
            file_paths,
            self.ui_queue
        )
        self.worker.start()

    def _start_ai_generation(self, cleaned_documents, ai_params):
        """Start AI summary generation after document cleaning is complete."""
        try:
            selected_model = ai_params["selected_model"]
            summary_length = ai_params["summary_length"]
            output_options = ai_params["output_options"]

            # Prepare combined text from cleaned documents
            combined_text = ""
            for doc in cleaned_documents:
                combined_text += f"\n\n--- {doc['filename']} ---\n{doc['cleaned_text']}"

            self.status_label.configure(text="Generating AI summary...")
            self.progress_bar.set(0.5)

            # Send task to AI worker - using the correct format expected by ollama_worker
            task_payload = {
                "case_text": combined_text,
                "max_words": summary_length,
                "preset_id": selected_model  # Use the selected model as preset
            }

            self.ai_worker_manager.send_task("GENERATE_SUMMARY", task_payload)
            debug_log(f"[MAIN WINDOW] Started AI generation with model: {selected_model}, length: {summary_length} words")

        except Exception as e:
            debug_log(f"[MAIN WINDOW] Error starting AI generation: {e}")
            messagebox.showerror("AI Generation Error", f"Failed to start AI summary generation: {str(e)}")
            self.select_files_btn.configure(state="normal")
            self.generate_outputs_btn.configure(state="normal")
            self.progress_bar.pack_forget()

    def _process_queue(self):
        """Process messages from the worker thread queue and AI worker manager."""
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

                elif message_type == 'processing_finished':
                    # Document cleaning finished; now generate AI summaries if requested
                    cleaned_documents = data
                    if self.pending_ai_generation:
                        self._start_ai_generation(cleaned_documents, self.pending_ai_generation)
                    else:
                        # No AI generation requested, just finish up
                        self.select_files_btn.configure(state="normal")
                        self.generate_outputs_btn.configure(state="normal")
                        self.progress_bar.pack_forget()
                        self.status_label.configure(text="Processing complete.")

                elif message_type == 'summary_result':
                    # AI summary generated successfully
                    debug_log(f"[MAIN WINDOW] Summary result received: {data}")
                    self.summary_results.update_outputs(meta_summary=data.get('summary', ''))
                    self.progress_bar.set(1.0)
                    self.status_label.configure(text="Summary generation complete!")
                    self.select_files_btn.configure(state="normal")
                    self.generate_outputs_btn.configure(state="normal")
                    self.progress_bar.pack_forget()
                    self.pending_ai_generation = None

                elif message_type == 'error':
                    messagebox.showerror("Processing Error", data)
                    self.select_files_btn.configure(state="normal")
                    self.generate_outputs_btn.configure(state="normal") # Re-enable new button
                    self.progress_bar.pack_forget()
                    self.pending_ai_generation = None

        except Empty:
            pass # No messages in queue
        finally:
            # Also check AI worker manager for messages
            if hasattr(self, 'ai_worker_manager'):
                ai_messages = self.ai_worker_manager.check_for_messages()
                for msg_type, msg_data in ai_messages:
                    # Put AI messages back in the main queue for processing
                    self.ui_queue.put((msg_type, msg_data))

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