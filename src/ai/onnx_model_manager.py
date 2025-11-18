"""
DEPRECATED: ONNX Model Manager for LocalScribe

⚠️ THIS MODULE IS DEPRECATED AND NO LONGER ACTIVELY USED
=========================================================

This file is kept for reference only. See development_log.md for details on why ONNX
was replaced with Ollama:

1. **Token Corruption Bug**: Phi-3 ONNX implementation had intermittent token
   generation errors producing garbled summaries in production.

2. **Platform Fragility**: ONNX Runtime GenAI requires:
   - Careful DLL initialization on Windows
   - Environment-specific setup and troubleshooting
   - Complex error handling for subprocess contexts

3. **Better Alternative**: Ollama provides:
   - Cross-platform stability (Windows/macOS/Linux identical behavior)
   - No compilation or DLL issues
   - Easier model management and switching
   - Better commercial viability (MIT license, no conflicts)

The OllamaModelManager in this module is the recommended replacement.
"""

import os
from pathlib import Path
from typing import Optional
import time

from ..config import MODELS_DIR, MAX_CONTEXT_TOKENS, PROMPTS_DIR
from ..prompt_config import get_prompt_config
from ..prompt_template_manager import PromptTemplateManager
from ..utils.logger import debug
from ..debug_logger import debug_log


class ONNXModelManager:
    """
    **DEPRECATED**: Manages ONNX-based AI models.

    ⚠️ **DO NOT USE** - Use OllamaModelManager instead.

    This class is kept for reference only. See module docstring for migration details.

    Original Purpose:
    Uses ONNX Runtime GenAI with DirectML for hardware-accelerated inference.
    Automatically detects and uses available GPU (integrated or dedicated).
    """

    def __init__(self):
        """Initialize the ONNX model manager."""
        self.current_model = None
        self.current_model_name: Optional[str] = None
        self.prompt_config = get_prompt_config()
        self.prompt_template_manager = PromptTemplateManager(PROMPTS_DIR)

        # Lazy import to avoid startup overhead
        self._onnxruntime_genai = None

    def _get_onnxruntime(self):
        """Lazy import of onnxruntime_genai."""
        if self._onnxruntime_genai is None:
            try:
                import onnxruntime_genai as og
                self._onnxruntime_genai = og
                debug("ONNX Runtime GenAI imported successfully")
            except (ImportError, OSError) as e:
                # ImportError: Module not found
                # OSError: WinError 1114 on Windows - DLL initialization failed
                # Both are expected failures when ONNX Runtime is not available or misconfigured
                debug(f"Failed to import onnxruntime_genai: {e}")
                raise RuntimeError(
                    "ONNX Runtime GenAI not available. "
                    "This can happen due to: (1) Package not installed, (2) DLL initialization failure on Windows, "
                    "or (3) Incompatible versions. Install with: pip install onnxruntime-genai-directml --pre"
                )
        return self._onnxruntime_genai

    def get_available_models(self) -> dict:
        """
        Check which ONNX models are available locally.

        Returns:
            dict: Model names mapped to availability status and paths
        """
        models = {
            'standard': {
                'name': 'Standard (Phi-3 DirectML)',
                'path': MODELS_DIR / 'phi-3-mini-onnx-directml' / 'directml' / 'directml-int4-awq-block-128',
                'size_gb': 2.3,
                'available': False,
                'description': 'GPU-accelerated (DirectML), very fast'
            },
            'standard_cpu': {
                'name': 'Standard (Phi-3 CPU)',
                'path': MODELS_DIR / 'phi-3-mini-onnx-cpu' / 'cpu_and_mobile' / 'cpu-int4-rtn-block-32-acc-level-4',
                'size_gb': 2.3,
                'available': False,
                'description': 'CPU-only fallback'
            }
        }

        # Check if model directories exist and contain required files
        for model_key, model_info in models.items():
            model_path = model_info['path']
            if model_path.exists():
                # Check for required ONNX files
                required_files = ['model.onnx', 'genai_config.json', 'tokenizer_config.json']
                if all((model_path / f).exists() for f in required_files):
                    model_info['available'] = True

                    # Calculate actual size
                    total_size = sum(
                        f.stat().st_size
                        for f in model_path.rglob('*')
                        if f.is_file()
                    )
                    model_info['size_gb'] = round(total_size / (1024**3), 1)

        return models

    def load_model(self, model_type: str = 'standard', verbose: bool = False) -> bool:
        """
        Load an ONNX model with DirectML or CPU execution provider.

        Args:
            model_type: Either 'standard' (DirectML) or 'standard_cpu' (CPU-only)
            verbose: Whether to print debug output

        Returns:
            bool: True if model loaded successfully, False otherwise
        """
        debug("Starting ONNX model loading...")
        debug_log(f"\n[ONNX MODEL LOAD] Starting load_model(model_type='{model_type}', verbose={verbose})")

        # Get model info
        models = self.get_available_models()
        if model_type not in models:
            debug(f"Invalid model type: {model_type}")
            return False

        model_info = models[model_type]

        # Check if model is available
        if not model_info['available']:
            debug(f"Model not found: {model_info['path']}")
            debug("Required files: model.onnx, genai_config.json, tokenizer_config.json")
            return False

        # Unload current model if loaded
        if self.current_model is not None:
            debug(f"Unloading current model: {self.current_model_name}")
            del self.current_model
            self.current_model = None
            self.current_model_name = None

        try:
            og = self._get_onnxruntime()

            debug(f"Loading model: {model_info['name']} from {model_info['path']}")

            # Load the ONNX model with Config
            # ONNX Runtime GenAI automatically selects the best execution provider
            # (DirectML for GPU, CPU for fallback)
            load_start = time.time()

            # Create config and model
            config = og.Config(str(model_info['path']))
            self.current_model = og.Model(config)

            load_time = time.time() - load_start

            # Get model metadata
            execution_provider = "DirectML" if "directml" in str(model_info['path']) else "CPU"

            self.current_model_name = model_type
            debug(f"Model loaded successfully in {load_time:.2f}s")
            debug(f"Execution provider: {execution_provider}")
            debug(f"Max context length: {MAX_CONTEXT_TOKENS}")

            return True

        except Exception as e:
            error_msg = f"Failed to load model: {str(e)}"
            debug(error_msg)
            debug_log(f"[ONNX MODEL LOAD ERROR] {error_msg}")

            # Also log the full traceback for debugging
            import traceback
            debug_log(f"[ONNX MODEL LOAD ERROR] Traceback:\n{traceback.format_exc()}")

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
        top_p: float = None
    ) -> str:
        """
        Generate text using the loaded ONNX model (non-streaming).

        Uses non-streaming generation to avoid tokenizer UTF-8 alignment issues.
        Returns complete text when generation finishes.

        Args:
            prompt: The input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0, lower = more deterministic)
            top_p: Nucleus sampling parameter

        Returns:
            str: Complete generated text

        Raises:
            RuntimeError: If no model is loaded
        """
        if not self.is_model_loaded():
            raise RuntimeError("No model loaded. Call load_model() first.")

        og = self._get_onnxruntime()

        # Use config defaults if not specified
        if temperature is None:
            temperature = self.prompt_config.summary_temperature
        if top_p is None:
            top_p = self.prompt_config.top_p

        debug(f"Generating text (max_tokens={max_tokens}, temp={temperature}, top_p={top_p})")
        debug_log("\n[ONNX MODEL] Starting generation (non-streaming)...")
        debug_log(f"[ONNX MODEL] Max tokens: {max_tokens}")
        debug_log(f"[ONNX MODEL] Prompt length: {len(prompt)} chars")
        debug_log("[ONNX MODEL] ===== COMPLETE PROMPT START =====")
        debug_log(prompt)
        debug_log("[ONNX MODEL] ===== COMPLETE PROMPT END =====")

        try:
            # Create tokenizer and encode prompt
            tokenizer = og.Tokenizer(self.current_model)
            input_tokens = tokenizer.encode(prompt)

            debug_log(f"[ONNX MODEL] Prompt tokenized: {len(input_tokens)} tokens")

            # Set up generation parameters
            # CRITICAL: Phi-3 Mini has 4096 token context window
            # max_length is total sequence length (input + output), so it cannot exceed context_length
            MODEL_CONTEXT_LENGTH = 4096
            safe_max_length = min(len(input_tokens) + max_tokens, MODEL_CONTEXT_LENGTH)

            # If input alone exceeds context, we have a problem
            if len(input_tokens) >= MODEL_CONTEXT_LENGTH:
                debug_log(f"[ONNX MODEL] WARNING: Input tokens ({len(input_tokens)}) >= context length ({MODEL_CONTEXT_LENGTH})")
                debug_log(f"[ONNX MODEL] Reducing max_length to {MODEL_CONTEXT_LENGTH}")

            search_options = {
                'max_length': safe_max_length,
                'temperature': temperature,
                'top_p': top_p,
                'do_sample': True  # Enable sampling for temperature/top_p to work
            }

            params = og.GeneratorParams(self.current_model)
            params.set_search_options(**search_options)

            # Create generator and append input tokens
            debug_log("[ONNX MODEL] Creating generator...")
            debug_log(f"[ONNX MODEL] Input tokens: {len(input_tokens)}, Max output tokens: {max_tokens}")

            generator = og.Generator(self.current_model, params)
            debug_log("[ONNX MODEL] Generator created, appending tokens...")

            generator.append_tokens(input_tokens)
            debug_log("[ONNX MODEL] Tokens appended successfully")

            debug_log("[ONNX MODEL] Starting token generation...")

            # Generate all tokens (non-streaming)
            token_count = 0
            while not generator.is_done():
                generator.generate_next_token()
                token_count += 1

                # Log every 50 tokens
                if token_count % 50 == 0:
                    debug_log(f"[ONNX MODEL] Generated {token_count} tokens so far...")

            # Decode complete output
            output_tokens = generator.get_sequence(0)

            # CRITICAL FIX: Use token indices to extract output, not string matching
            # The complete sequence is: [input_tokens] + [output_tokens]
            # We need to extract output_tokens without UTF-8 alignment issues

            num_input_tokens = len(input_tokens)
            num_output_tokens = len(output_tokens) - num_input_tokens

            # Extract only the output token IDs (skip the input tokens)
            output_token_ids = output_tokens[num_input_tokens:]

            debug_log(f"[ONNX MODEL] First 50 output token IDs: {output_token_ids[:50]}")
            debug_log(f"[ONNX MODEL] Last 20 output token IDs: {output_token_ids[-20:]}")

            # Decode ONLY the output tokens
            output_text = tokenizer.decode(output_token_ids)

            # Also decode the complete sequence for diagnostics
            complete_text = tokenizer.decode(output_tokens)
            input_text = tokenizer.decode(input_tokens)

            debug_log(f"[ONNX MODEL] Generation complete: {num_output_tokens} output tokens")
            debug_log(f"[ONNX MODEL] Input tokens: {num_input_tokens}, Output tokens: {num_output_tokens}")
            debug_log(f"[ONNX MODEL] Input text length: {len(input_text)} chars")
            debug_log(f"[ONNX MODEL] Complete sequence length: {len(complete_text)} chars")
            debug_log(f"[ONNX MODEL] Decoded output text length: {len(output_text)} chars")
            debug_log(f"[ONNX MODEL] Output preview (first 100 chars): {output_text[:100]}")

            return output_text.strip()

        except Exception as e:
            debug(f"Text generation failed: {str(e)}")
            debug_log(f"[ONNX MODEL] ERROR: {str(e)}")
            import traceback
            debug_log(f"[ONNX MODEL] Traceback:\n{traceback.format_exc()}")
            raise RuntimeError(f"Text generation failed: {str(e)}")

    def generate_summary(
        self,
        case_text: str,
        max_words: int = 200,
        preset_id: str = "factual-summary"
    ) -> str:
        """
        Generate a case summary from cleaned document text.

        Returns complete summary text in one go. For UI feedback, use a
        progress indicator in the GUI rather than streaming output.

        Args:
            case_text: The cleaned case document text
            max_words: Target summary length in words (100-500)
            preset_id: Template preset to use (e.g., 'factual-summary', 'strategic-analysis')

        Returns:
            str: Complete summary text
        """
        # Get word count range from config
        min_words, max_words_range = self.prompt_config.get_word_count_range(max_words)

        # Load and format prompt template using PromptTemplateManager
        # Model identifier is 'phi-3-mini' (hardcoded for now, can be made configurable later)
        model_id = "phi-3-mini"

        try:
            template = self.prompt_template_manager.load_template(model_id, preset_id)
            prompt = self.prompt_template_manager.format_template(
                template=template,
                min_words=min_words,
                max_words=max_words,
                max_words_range=max_words_range,
                case_text=case_text
            )
        except FileNotFoundError as e:
            debug(f"Template not found: {e}. Falling back to default.")
            # Fallback to factual-summary if requested preset doesn't exist
            template = self.prompt_template_manager.load_template(model_id, "factual-summary")
            prompt = self.prompt_template_manager.format_template(
                template=template,
                min_words=min_words,
                max_words=max_words,
                max_words_range=max_words_range,
                case_text=case_text
            )

        # Estimate tokens using config values with buffer to prevent mid-sentence cutoffs
        tokens_per_word = self.prompt_config.tokens_per_word
        buffer_multiplier = self.prompt_config.token_buffer_multiplier
        max_tokens = int(max_words_range * tokens_per_word * buffer_multiplier)

        # Generate summary (temperature and top_p will use config defaults)
        return self.generate_text(
            prompt=prompt,
            max_tokens=max_tokens
        )

    def unload_model(self):
        """Unload the current model from memory."""
        if self.current_model is not None:
            debug(f"Unloading model: {self.current_model_name}")
            del self.current_model
            self.current_model = None
            self.current_model_name = None
