"""
ONNX Model Manager for LocalScribe
Handles loading and managing Phi-3 ONNX models with DirectML acceleration.

This is the next-generation model manager optimized for Windows with:
- DirectML GPU acceleration (works with integrated GPUs)
- INT4-AWQ quantization (better quality than Q4_K_M)
- 5-10x faster generation than llama-cpp-python
"""

import os
from pathlib import Path
from typing import Optional, Iterator
import time

from ..config import MODELS_DIR, MAX_CONTEXT_TOKENS
from ..prompt_config import get_prompt_config
from ..utils.logger import debug
from ..debug_logger import debug_log


class ONNXModelManager:
    """
    Manages ONNX-based AI models for case summarization.

    Uses ONNX Runtime GenAI with DirectML for hardware-accelerated inference.
    Automatically detects and uses available GPU (integrated or dedicated).
    """

    def __init__(self):
        """Initialize the ONNX model manager."""
        self.current_model = None
        self.current_model_name: Optional[str] = None
        self.prompt_config = get_prompt_config()

        # Lazy import to avoid startup overhead
        self._onnxruntime_genai = None

    def _get_onnxruntime(self):
        """Lazy import of onnxruntime_genai."""
        if self._onnxruntime_genai is None:
            try:
                import onnxruntime_genai as og
                self._onnxruntime_genai = og
                debug("ONNX Runtime GenAI imported successfully")
            except ImportError as e:
                debug(f"Failed to import onnxruntime_genai: {e}")
                raise RuntimeError(
                    "ONNX Runtime GenAI not installed. "
                    "Install with: pip install onnxruntime-genai-directml"
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
        top_p: float = None,
        stream: bool = True
    ) -> Iterator[str]:
        """
        Generate text using the loaded ONNX model with streaming.

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

        og = self._get_onnxruntime()

        # Use config defaults if not specified
        if temperature is None:
            temperature = self.prompt_config.summary_temperature
        if top_p is None:
            top_p = self.prompt_config.top_p

        debug(f"Generating text (max_tokens={max_tokens}, temp={temperature}, top_p={top_p})")
        debug_log("\n[ONNX MODEL] Starting generation...")
        debug_log(f"[ONNX MODEL] Stream mode: {stream}")
        debug_log(f"[ONNX MODEL] Max tokens: {max_tokens}")
        debug_log(f"[ONNX MODEL] Prompt length: {len(prompt)} chars")
        debug_log(f"[ONNX MODEL] First 200 chars of prompt:\n{prompt[:200]}")

        try:
            # Create tokenizer and encode prompt
            tokenizer = og.Tokenizer(self.current_model)
            input_tokens = tokenizer.encode(prompt)

            debug_log(f"[ONNX MODEL] Prompt tokenized: {len(input_tokens)} tokens")

            # Set up generation parameters
            search_options = {
                'max_length': len(input_tokens) + max_tokens,
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

            if stream:
                # Stream mode: yield tokens as they're generated
                token_num = 0
                tokenizer_stream = tokenizer.create_stream()

                while not generator.is_done():
                    generator.generate_next_token()

                    # Decode the new token using streaming decoder
                    new_token_id = generator.get_next_tokens()[0]
                    new_token_text = tokenizer_stream.decode(new_token_id)

                    token_num += 1

                    if token_num <= 5 or token_num % 20 == 0:
                        debug_log(f"[ONNX MODEL] Token #{token_num}: '{new_token_text}'")

                    yield new_token_text

                debug_log(f"[ONNX MODEL] Generation complete: {token_num} tokens")

            else:
                # Non-stream mode: generate all tokens then return complete text
                while not generator.is_done():
                    generator.generate_next_token()

                output_tokens = generator.get_sequence(0)
                # Decode only the new tokens (excluding input)
                output_text = tokenizer.decode(output_tokens[len(input_tokens):])

                debug_log(f"[ONNX MODEL] Generation complete: {len(output_tokens) - len(input_tokens)} tokens")
                return output_text

        except Exception as e:
            debug(f"Text generation failed: {str(e)}")
            debug_log(f"[ONNX MODEL] ERROR: {str(e)}")
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
