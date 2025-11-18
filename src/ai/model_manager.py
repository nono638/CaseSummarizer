"""
DEPRECATED: Llama-CPP Model Manager for LocalScribe

⚠️ THIS MODULE IS DEPRECATED AND NO LONGER ACTIVELY USED
=========================================================

This is a legacy implementation kept for reference only. It used llama-cpp-python
to manage GGUF format models.

Migration Notes:
The OllamaModelManager (src/ai/ollama_model_manager.py) is the recommended replacement.
It provides better cross-platform stability and easier model management.

Original Purpose:
Handles loading and managing Gemma 2 GGUF models for case summarization via llama-cpp-python.
"""

import os
from pathlib import Path
from typing import Optional, Iterator
from llama_cpp import Llama

from ..config import (
    MODELS_DIR,
    STANDARD_MODEL_NAME,
    PRO_MODEL_NAME,
    MAX_CONTEXT_TOKENS,
)
from ..prompt_config import get_prompt_config
from ..utils.logger import debug
from ..debug_logger import debug_log


class ModelManager:
    """
    Manages AI models for case summarization.

    Supports two model variants:
    - Standard: gemma-2-9b-it-q4_k_m.gguf (~7GB) - Fast, good quality
    - Pro: gemma-2-27b-it-q4_k_m.gguf (~22GB) - Slower, best quality
    """

    def __init__(self):
        """Initialize the model manager."""
        self.current_model: Optional[Llama] = None
        self.current_model_name: Optional[str] = None
        self.prompt_config = get_prompt_config()

    def get_available_models(self) -> dict:
        """
        Check which models are available locally.

        Returns:
            dict: Model names mapped to availability status and file paths
            Example: {
                'standard': {'available': True, 'path': Path(...), 'size_gb': 7},
                'pro': {'available': False, 'path': Path(...), 'size_gb': 22}
            }
        """
        models = {
            'standard': {
                'name': 'Standard (Phi-3 3.8B)',
                'filename': STANDARD_MODEL_NAME,
                'path': MODELS_DIR / STANDARD_MODEL_NAME,
                'size_gb': 2.3,
                'available': False,
                'description': 'CPU-optimized, fast (30-90 sec)'
            },
            'pro': {
                'name': 'Pro (Gemma 2 9B)',
                'filename': PRO_MODEL_NAME,
                'path': MODELS_DIR / PRO_MODEL_NAME,
                'size_gb': 5.4,
                'available': False,
                'description': 'Best quality (GPU recommended)'
            }
        }

        # Check if model files exist
        for model_key, model_info in models.items():
            if model_info['path'].exists():
                model_info['available'] = True
                # Get actual file size
                size_bytes = model_info['path'].stat().st_size
                model_info['size_gb'] = round(size_bytes / (1024**3), 1)

        return models

    def load_model(self, model_type: str = 'standard', verbose: bool = False) -> bool:
        """
        Load a GGUF model into memory.

        Args:
            model_type: Either 'standard' or 'pro'
            verbose: Whether to print llama.cpp debug output

        Returns:
            bool: True if model loaded successfully, False otherwise
        """
        debug("Starting model loading...")

        # Get model info
        models = self.get_available_models()
        if model_type not in models:
            debug(f"Invalid model type: {model_type}")
            return False

        model_info = models[model_type]

        # Check if model file exists
        if not model_info['available']:
            debug(f"Model file not found: {model_info['path']}")
            return False

        # Unload current model if loaded
        if self.current_model is not None:
            debug(f"Unloading current model: {self.current_model_name}")
            del self.current_model
            self.current_model = None
            self.current_model_name = None

        try:
            debug(f"Loading model: {model_info['name']} from {model_info['path']}")

            # Determine optimal thread count for CPU inference
            # Research shows: n_threads should be physical cores, n_threads_batch can be logical cores
            # This prevents thread doubling and lockstep synchronization issues
            logical_cores = os.cpu_count() or 4

            # Estimate physical cores for hardware-agnostic compatibility
            # Most modern CPUs use 2-way SMT (Intel HT, AMD SMT)
            # Single-threaded CPUs: physical_cores = logical_cores (safe)
            # Hyperthreaded CPUs: physical_cores ≈ logical_cores / 2 (optimal)
            physical_cores = max(1, logical_cores // 2)

            debug(f"Thread config: {physical_cores} threads (prompt), {logical_cores} threads (batch)")

            # Load model with llama-cpp-python with optimized CPU settings
            self.current_model = Llama(
                model_path=str(model_info['path']),
                n_ctx=MAX_CONTEXT_TOKENS,
                n_threads=physical_cores,      # Physical cores for prompt processing
                n_threads_batch=logical_cores,  # All cores for token generation
                n_batch=512,                    # Batch size for better throughput
                verbose=verbose
            )

            self.current_model_name = model_type
            debug(f"Model loaded successfully: {model_info['name']}")
            return True

        except Exception as e:
            debug(f"Failed to load model: {str(e)}")
            self.current_model = None
            self.current_model_name = None
            return False

    def is_model_loaded(self) -> bool:
        """Check if a model is currently loaded."""
        return self.current_model is not None

    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = None,
        top_p: float = None,
        stream: bool = True
    ) -> Iterator[str]:
        """
        Generate text using the loaded model with streaming.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0, lower = more deterministic)
            top_p: Nucleus sampling parameter
            stream: Whether to stream output (yields tokens as they're generated)

        Yields:
            str: Generated text tokens (if stream=True)

        Returns:
            str: Complete generated text (if stream=False)

        Raises:
            RuntimeError: If no model is loaded
        """
        if not self.is_model_loaded():
            raise RuntimeError("No model loaded. Call load_model() first.")

        # Use config defaults if not specified
        if temperature is None:
            temperature = self.prompt_config.summary_temperature
        if top_p is None:
            top_p = self.prompt_config.top_p

        debug(f"Generating text (max_tokens={max_tokens}, temp={temperature}, top_p={top_p})")
        debug_log("\n[MODEL] Starting generation...")
        debug_log(f"[MODEL] Stream mode: {stream}")
        debug_log(f"[MODEL] Max tokens: {max_tokens}")
        debug_log(f"[MODEL] Prompt length: {len(prompt)} chars")
        debug_log(f"[MODEL] First 200 chars of prompt:\n{prompt[:200]}")

        try:
            debug_log("[MODEL] Calling llama.cpp model... (this may take 2-3 minutes for first token)")
            response = self.current_model(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stream=stream,
                stop=["</s>", "\n\n\n"]  # Stop sequences
            )
            debug_log("[MODEL] Model call returned, starting to iterate response...")

            if stream:
                # Stream mode: yield tokens as they're generated
                token_num = 0
                for output in response:
                    token = output['choices'][0]['text']
                    token_num += 1
                    if token_num <= 5 or token_num % 20 == 0:
                        debug_log(f"[MODEL] Yielding token #{token_num}: '{token}'")
                    yield token
                debug_log(f"[MODEL] Finished generating {token_num} tokens")
            else:
                # Non-stream mode: return complete text
                return response['choices'][0]['text']

        except Exception as e:
            debug(f"Text generation failed: {str(e)}")
            raise RuntimeError(f"Text generation failed: {str(e)}")

    def generate_summary(
        self,
        case_text: str,
        max_words: int = 200,
        stream: bool = True
    ) -> Iterator[str]:
        """
        Generate a case summary from cleaned document text.

        Args:
            case_text: The cleaned case document text
            max_words: Target summary length in words (100-500)
            stream: Whether to stream output

        Yields:
            str: Summary text tokens (if stream=True)

        Returns:
            str: Complete summary (if stream=False)
        """
        # Get word count range from config
        min_words, max_words_range = self.prompt_config.get_word_count_range(max_words)

        # Construct prompt for case summarization
        # Based on specification Section 7.3
        prompt = f"""You are a legal case summarizer. Write a clear, concise summary of the following legal document.

Instructions:
- Length: Between {min_words} and {max_words_range} words (target: {max_words} words)
- Focus on: key facts, parties involved, legal issues, and outcomes
- Use plain language (avoid legalese when possible)
- Be objective and factual

Document:
{case_text}

Summary:"""

        # Estimate tokens using config value
        tokens_per_word = self.prompt_config.tokens_per_word
        max_tokens = int(max_words_range * tokens_per_word)

        # Generate summary (temperature and top_p will use config defaults)
        return self.generate_text(
            prompt=prompt,
            max_tokens=max_tokens,
            stream=stream
        )

    def unload_model(self):
        """Unload the current model from memory."""
        if self.current_model is not None:
            debug(f"Unloading model: {self.current_model_name}")
            del self.current_model
            self.current_model = None
            self.current_model_name = None
