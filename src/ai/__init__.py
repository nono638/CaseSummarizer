"""
LocalScribe AI Module
Handles AI model loading and text generation.
"""

# CRITICAL: Import onnxruntime_genai BEFORE PySide6/Qt to avoid DLL conflicts on Windows
# See: https://github.com/pytorch/pytorch/issues/166628
try:
    import onnxruntime_genai as _og
    _ONNX_AVAILABLE = True
except ImportError:
    _ONNX_AVAILABLE = False

# New ONNX-based model manager (recommended for Windows with DirectML)
from .onnx_model_manager import ONNXModelManager

# Legacy llama-cpp model manager (for reference/fallback)
from .model_manager import ModelManager as LlamaCppModelManager

# Default to ONNX model manager for better performance
ModelManager = ONNXModelManager

__all__ = ['ModelManager', 'ONNXModelManager', 'LlamaCppModelManager']
