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

from src.ui.widgets import FileReviewTable, AIControlsWidget, SummaryResultsWidget
from src.ui.workers import ProcessingWorker
from src.cleaner import DocumentCleaner
from src.ai import ModelManager
from src.debug_logger import debug_log

class MainWindow(ctk.CTk):
    """
    Main application window for LocalScribe, refactored with CustomTkinter.
    """

    def __init__(self):
        super().__init__()
        self.title("LocalScribe - Legal Document Processor")
        self.geometry("1100x750")

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

    def _create_main_layout(self):
        """Creates the main grid layout."""
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _create_menus(self):
        """Create a native-style menubar using tkinter.Menu."""
        self.menubar = Menu(self)
        self.config(menu=self.menubar)
        file_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Select Files...", command=self.select_files)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        help_menu = Menu(self.menubar, tearoff=0)
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
        """Create central widget with file review table and controls."""
        self.main_content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_content_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.main_content_frame.grid_columnconfigure(0, weight=3)
        self.main_content_frame.grid_columnconfigure(1, weight=1)
        self.main_content_frame.grid_rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkFrame(self.main_content_frame)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.left_frame.grid_rowconfigure(0, weight=2)
        self.left_frame.grid_rowconfigure(1, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)
        
        self.file_table = FileReviewTable(self.left_frame)
        self.file_table.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        self.summary_results = SummaryResultsWidget(self.left_frame)
        self.summary_results.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        self.right_frame = ctk.CTkFrame(self.main_content_frame, width=300)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        
        self.ai_controls = AIControlsWidget(self.right_frame, self.model_manager)
        self.ai_controls.pack(expand=True, fill="both", padx=5, pady=5)

    def _create_status_bar(self):
        """Create status bar for messages."""
        self.status_bar_frame = ctk.CTkFrame(self, height=25, corner_radius=0)
        self.status_bar_frame.grid(row=2, column=0, sticky="ew")
        self.status_label = ctk.CTkLabel(self.status_bar_frame, text="Ready", anchor="w")
        self.status_label.pack(side="left", padx=10)
        
        self.progress_bar = ctk.CTkProgressBar(self.status_bar_frame, mode="determinate")
        self.progress_bar.set(0)
        
    def select_files(self):
        """Open file dialog and start processing."""
        filepaths = filedialog.askopenfilenames(
            title="Select Legal Documents",
            filetypes=(("Documents", "*.pdf *.txt *.rtf"), ("All files", "*.*"))
        )
        if filepaths:
            self.selected_files = filepaths
            self.files_label.configure(text=f"{len(filepaths)} file(s) selected")
            self.start_processing(filepaths)

    def start_processing(self, file_paths):
        """Start background processing of selected documents."""
        self.select_files_btn.configure(state="disabled")
        self.progress_bar.pack(side="right", padx=10, pady=5, fill="x", expand=True)
        self.file_table.clear()
        self.processing_results = []

        self.worker = ProcessingWorker(file_paths, self.ui_queue)
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

                elif message_type == 'finished':
                    self.select_files_btn.configure(state="normal")
                    self.progress_bar.pack_forget()
                    self.status_label.configure(text="Processing complete.")
                
                elif message_type == 'error':
                    messagebox.showerror("Processing Error", data)
                    self.select_files_btn.configure(state="normal")
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