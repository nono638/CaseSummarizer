"""
LocalScribe - Background Workers (CustomTkinter Refactor)
"""
import threading
import multiprocessing
import time
import os
import traceback
from queue import Queue, Empty
from pathlib import Path

from src.cleaner import DocumentCleaner
from src.debug_logger import debug_log
from src.progressive_summarizer import ProgressiveSummarizer
from src.vocabulary_extractor import VocabularyExtractor

class ProcessingWorker(threading.Thread):
    """
    Background worker for processing documents, generating summaries,
    meta-summaries, and vocabulary lists.
    Communicates with the main UI via a queue.
    """
    def __init__(self, file_paths, ui_queue, model_manager, selected_model, summary_length, output_options, jurisdiction="ny"):
        super().__init__(daemon=True)
        self.file_paths = file_paths
        self.ui_queue = ui_queue
        self.model_manager = model_manager
        self.selected_model = selected_model
        self.summary_length = summary_length
        self.output_options = output_options
        self.jurisdiction = jurisdiction
        
        self.cleaner = DocumentCleaner(jurisdiction=self.jurisdiction)
        self.summarizer = ProgressiveSummarizer()
        self.vocabulary_extractor = VocabularyExtractor()

    def run(self):
        """Execute document processing and AI generation in background thread."""
        try:
            total_files = len(self.file_paths)
            all_summaries_data = [] # To collect data for meta-summary and vocab CSV
            all_processed_text = [] # To collect all cleaned text for vocab extractor

            for idx, file_path in enumerate(self.file_paths):
                percentage = int((idx / total_files) * 100)
                filename = os.path.basename(file_path)
                
                self.ui_queue.put(('progress', (percentage, f"Processing and cleaning {filename}...")))

                def progress_callback(msg):
                    self.ui_queue.put(('progress', (percentage, msg)))

                cleaned_result = self.cleaner.process_document(file_path, progress_callback=progress_callback)
                
                if cleaned_result['status'] == 'success':
                    all_processed_text.append(cleaned_result['cleaned_text'])

                    individual_summary = ""
                    if self.output_options["individual_summaries"]:
                        self.ui_queue.put(('progress', (percentage, f"Generating summary for {filename}...")))
                        try:
                            # Chunk document
                            doc_chunks = self.summarizer.chunk_document(cleaned_result['cleaned_text'])
                            self.summarizer.prepare_chunks_dataframe(doc_chunks)

                            # Create prompt
                            summary_prompt = self.summarizer.create_summarization_prompt(
                                chunk_num=1, # For full document, we treat it as one 'chunk' for initial prompt
                                chunk_text=cleaned_result['cleaned_text'],
                                summary_target_words=self.summary_length
                            )
                            individual_summary = self.model_manager.generate_text(self.selected_model, summary_prompt)
                            
                        except Exception as e:
                            debug_log(f"Error generating individual summary for {filename}: {e}")
                            individual_summary = f"Error generating summary: {e}"
                    
                    # Store summary for meta-summary and vocab processing
                    all_summaries_data.append({
                        'title': filename,
                        'summary': individual_summary,
                        'keywords': [] # Keywords will be extracted later if needed, or by vocab extractor
                    })
                    
                    cleaned_result['summary'] = individual_summary # Add summary to result
                    self.ui_queue.put(('file_processed', cleaned_result))
                else:
                    self.ui_queue.put(('file_processed', cleaned_result)) # Still send result even if cleaning failed


            # --- Post-processing: Meta-Summary and Vocabulary CSV ---
            self.ui_queue.put(('progress', (95, "Finalizing outputs...")))

            if self.output_options["meta_summary"]:
                self.ui_queue.put(('progress', (96, "Generating meta-summary...")))
                try:
                    meta_summary_metadata = self.summarizer.generate_summary_metadata(all_summaries_data)
                    meta_summary_prompt = f"Based on the following document summaries and their metadata, provide a concise meta-summary of key themes and overall sentiment:\n\nSummaries: {all_summaries_data}\n\nMetadata: {meta_summary_metadata}\n\nMeta-Summary:"
                    meta_summary = self.model_manager.generate_text(self.selected_model, meta_summary_prompt)
                    self.ui_queue.put(('meta_summary_generated', meta_summary))
                except Exception as e:
                    debug_log(f"Error generating meta-summary: {e}")
                    self.ui_queue.put(('meta_summary_generated', f"Error generating meta-summary: {e}"))

            if self.output_options["vocab_csv"]:
                self.ui_queue.put(('progress', (98, "Extracting rare words...")))
                try:
                    combined_text = "\n\n".join(all_processed_text)
                    vocab_results = self.vocabulary_extractor.extract(combined_text)
                    
                    # Convert to list of lists for CSV format
                    csv_data = [["Term", "Type", "Relevance", "Definition", "Frequency"]]
                    for term_data in vocab_results:
                        csv_data.append([
                            term_data.get('term', ''),
                            term_data.get('type', ''),
                            term_data.get('relevance', ''),
                            term_data.get('definition', ''),
                            str(term_data.get('frequency', ''))
                        ])
                    self.ui_queue.put(('vocab_csv_generated', csv_data))
                except Exception as e:
                    debug_log(f"Error extracting vocabulary: {e}")
                    self.ui_queue.put(('vocab_csv_generated', f"Error extracting vocabulary: {e}"))

            self.ui_queue.put(('progress', (100, "Processing complete")))
            self.ui_queue.put(('finished', None))

        except Exception as e:
            debug_log(f"ProcessingWorker encountered a critical error: {e}\n{traceback.format_exc()}")
            self.ui_queue.put(('error', f"Critical processing error: {str(e)}"))


