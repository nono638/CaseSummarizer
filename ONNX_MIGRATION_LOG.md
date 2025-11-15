# ONNX Runtime Migration - Detailed Technical Log
**Date:** 2025-11-15
**Branch:** phase3-enhancements
**Status:** ⚠️ BACKEND WORKING, GUI DISPLAY ISSUES UNRESOLVED

---

## Summary

Successfully migrated AI backend from llama-cpp-python to ONNX Runtime GenAI with DirectML for 5.4x performance improvement. **Backend generation works perfectly** (verified via file output), but GUI text display has unresolved threading/update issues causing freezing.

---

## Performance Results

| Metric | llama-cpp-python | ONNX DirectML | Improvement |
|--------|------------------|---------------|-------------|
| Model load time | ~5 seconds | 2.3 seconds | 2.2x faster |
| First token time | 177 seconds | 16 seconds | 11x faster |
| Generation speed | 0.6 tokens/sec | 3.21 tokens/sec | 5.4x faster |
| 100-word summary | 4+ minutes | ~56 seconds | 4.3x faster |

---

## What Worked

### 1. ONNX Runtime Installation
```bash
pip install onnxruntime-genai-directml>=0.10.0
pip install huggingface-hub>=0.20.0
```

### 2. Model Download
Downloaded Phi-3 Mini ONNX INT4-AWQ model from HuggingFace:
- Path: `microsoft/Phi-3-mini-4k-instruct-onnx`
- Variant: `directml/directml-int4-awq-block-128`
- Size: 2.0 GB
- Location: `%APPDATA%\LocalScribe\models\phi-3-mini-onnx-directml\`

Used Python API (huggingface-cli didn't work):
```python
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="microsoft/Phi-3-mini-4k-instruct-onnx",
    allow_patterns=["directml/*"],
    local_dir=str(models_dir / "phi-3-mini-onnx-directml"),
    local_dir_use_symlinks=False
)
```

### 3. Created ONNXModelManager (`src/ai/onnx_model_manager.py`)
New model manager using ONNX Runtime GenAI API:
- Loads models with `og.Config()` and `og.Model()`
- Streaming generation with `og.Generator()` and `generator.generate_next_token()`
- Compatible with existing ModelManager interface
- Automatic DirectML/CPU detection

### 4. Fixed DLL Initialization Conflict
**Critical Fix:** Import order matters on Windows!

**Problem:** `OSError: [WinError 1114] A dynamic link library (DLL) initialization routine failed`

**Root Cause:** PySide6/Qt loads DLLs that conflict with DirectML when imported first

**Solution:** Import `onnxruntime_genai` BEFORE any PySide6/Qt imports

Changes made:
- `src/ai/__init__.py`: Added early import of `onnxruntime_genai`
- `src/main.py`: Added `import src.ai` before PySide6 imports

```python
# src/main.py
import sys
# CRITICAL: Import src.ai BEFORE PySide6
import src.ai  # noqa: F401
from PySide6.QtWidgets import QApplication
```

This is a known issue with PyTorch/Qt on Windows - same solution applies to ONNX Runtime.

### 5. Optimized Thread Configuration
Fixed thread configuration for CPU inference:
```python
logical_cores = os.cpu_count() or 4
physical_cores = max(1, logical_cores // 2)

self.current_model = Llama(
    n_threads=physical_cores,      # Prompt processing
    n_threads_batch=logical_cores,  # Token generation
    n_batch=512
)
```

### 6. Input Size Optimization
Reduced max input from 1500 words to 300 words:
- 1500 words → 3397 tokens → Generator creation hangs for 90+ seconds
- 300 words → 788 tokens → Generator creation takes <1 second

File: `src/ui/workers.py:274`

### 7. Backend Verification
**Generation confirmed working** via file output (`generated_summary.txt`):
- 180 tokens generated successfully
- Coherent legal summary produced
- Proper formatting and content

---

## What Didn't Work

### Attempt 1: QTextCursor-based Text Insertion ❌
**File:** `src/ui/widgets.py:638-641` (original)

```python
cursor = self.summary_text.textCursor()
cursor.movePosition(QTextCursor.MoveOperation.End)
cursor.insertText(token)
self.summary_text.setTextCursor(cursor)
```

**Problem:** Text never appeared in widget. Debug log showed `toPlainText()` always returned empty string (length 0).

### Attempt 2: Direct insertPlainText() ❌
**File:** `src/ui/widgets.py:647-648` (attempted fix)

```python
self.summary_text.moveCursor(QTextCursor.MoveOperation.End)
self.summary_text.insertPlainText(token)
```

**Problem:** Still no text display. GUI became unresponsive.

### Attempt 3: Streaming Token Display ❌
**Issue:** 180+ rapid GUI updates (one per token, ~0.2-0.4 seconds apart) overwhelm Qt event loop

**Symptoms:**
- GUI freezes and becomes "Not Responding"
- Progress bar appears late or not at all
- Text widget stays blank even though `append_token()` is called

**Debug Evidence** (`debug_flow.txt`):
- Lines 53-284 show `[GUI append_token]` called 180+ times
- Every call shows `current length: 0` - text not persisting
- Worker thread sends tokens correctly
- Signal/slot connection works
- But GUI updates fail

**Root Cause:** Qt threading issue - either:
1. Too many rapid main-thread updates blocking event loop
2. Widget state being corrupted between updates
3. Some Qt-internal buffering/batching issue

---

## Current Workaround

**Disabled streaming token display** to prevent GUI freezing:

**File:** `src/ui/main_window.py:506`
```python
# NOTE: Disabled streaming token display to prevent GUI freezing
# self.ai_worker.token_generated.connect(self._on_token_generated)
```

**Current Behavior:**
- Summary generated successfully in background
- Saved to `generated_summary.txt` for verification
- GUI should show complete summary when done (via `summary_complete` signal)
- **But GUI still freezes** - even without streaming updates!

---

## Unresolved Issues

### GUI Freezing During Generation
**Status:** BLOCKING

**Symptoms:**
- GUI becomes "Not Responding" when "Generate Summaries" is clicked
- Happens even with streaming disabled
- Progress bar may not appear
- Summary doesn't display in GUI

**What We Know:**
1. ✅ Backend works perfectly (file output confirms)
2. ✅ Worker thread runs correctly
3. ✅ Signals are emitted
4. ❌ GUI thread becomes blocked somehow

**Possible Causes:**
1. Generator creation (`og.Generator()`) takes 40+ seconds and might be blocking despite QThread
2. Token appending (`generator.append_tokens()`) takes 40+ seconds
3. Some synchronous operation in ONNX Runtime blocking Qt event loop
4. Qt's processEvents() not being called during long operations

**Next Steps to Try:**
1. Add `QApplication.processEvents()` calls during generation
2. Use QTimer-based polling instead of signals
3. Run generation in separate process instead of thread
4. Investigate if ONNX Runtime has async API
5. Check if DirectML initialization is blocking main thread

---

## Files Changed

### New Files
- `src/ai/onnx_model_manager.py` - ONNX-based model manager
- `download_onnx_models.py` - Model download script
- `test_onnx_model.py` - Performance test script
- `generated_summary.txt` - Debug output file

### Modified Files
- `src/ai/__init__.py` - Added early onnxruntime_genai import, made ONNXModelManager default
- `src/main.py` - Import src.ai before PySide6 to fix DLL conflict
- `src/ui/workers.py` - Reduced input size to 300 words, added file output
- `src/ui/widgets.py` - Multiple attempts at text insertion (all failed)
- `src/ui/main_window.py` - Disabled streaming token connection
- `requirements.txt` - Added onnxruntime-genai-directml, huggingface-hub

---

## Technical Insights

### DirectML on Integrated GPUs
- DirectML works with **any DirectX 12 GPU** (Intel/AMD integrated, not just NVIDIA)
- Provides 5-10x speedup over pure CPU inference
- No CUDA required
- Ideal for business deployment on standard laptops

### ONNX vs GGUF
- ONNX INT4-AWQ quantization preserves quality better than Q4_K_M GGUF
- Microsoft's official deployment path for Phi-3 on Windows
- Pre-compiled, optimized kernels vs generic llama.cpp
- Faster load times, faster inference

### Qt Threading Lessons
- DLL load order matters on Windows - always load heavy DLLs before Qt
- Too many rapid GUI updates can freeze event loop even with proper threading
- Signals/slots don't automatically prevent UI blocking from long operations
- May need explicit `processEvents()` calls or different threading approach

---

## Recommendations

**For Next Session:**

1. **Fix GUI Freezing (Priority 1)**
   - Try QApplication.processEvents() during generation
   - Consider separate process instead of QThread
   - Investigate ONNX Runtime async capabilities

2. **Simplify Display (If GUI unfixable)**
   - Show only final summary (no streaming)
   - Add "Please wait..." dialog during generation
   - Save summaries to file as primary workflow

3. **Test on Different Hardware**
   - Verify DirectML works on AMD integrated GPUs
   - Test on machines without DirectX 12
   - Benchmark CPU fallback performance

4. **Consider Alternatives**
   - Try onnxruntime-directml (non-genai) if issue persists
   - Investigate if PyQt6 has better threading than PySide6
   - Consider web-based UI (Flask/FastAPI) instead of Qt

---

## Testing Commands

**Test ONNX Model (Standalone):**
```bash
python test_onnx_model.py
```
Expected: 3-6 tokens/sec, completes in ~1 minute

**Check Generated Summary:**
```
# After running GUI, check:
generated_summary.txt
```

**View Debug Logs:**
```
debug_flow.txt
```

---

**Session End:** GUI display issues remain unresolved despite backend working perfectly.
