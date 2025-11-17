"""
Simple ONNX Runtime DirectML test - isolate model configuration issues
This script tests basic inference without complex prompting or streaming
"""

import sys
sys.path.insert(0, '.')

from src.ai import ModelManager
from src.debug_logger import debug_log
import time

def test_simple_inference():
    """Test with a very simple prompt to isolate configuration issues"""

    print("\n" + "="*70)
    print("SIMPLE ONNX RUNTIME TEST")
    print("="*70)

    # Initialize model manager
    print("\n[TEST] Initializing model manager...")
    model_mgr = ModelManager()

    # Load model
    print("[TEST] Loading DirectML model...")
    load_start = time.time()
    success = model_mgr.load_model('standard', verbose=True)
    load_time = time.time() - load_start

    if not success:
        print("[ERROR] Model failed to load!")
        return

    print(f"[SUCCESS] Model loaded in {load_time:.2f}s")

    # Test 1: Ultra-simple prompt (non-streaming)
    print("\n" + "-"*70)
    print("TEST 1: Ultra-simple prompt (non-streaming)")
    print("-"*70)

    simple_prompt = "Summarize this: The quick brown fox jumps over the lazy dog.\nSummary:"

    print(f"\nPrompt: {simple_prompt}")
    print("\nGenerating response (non-streaming)...")

    gen_start = time.time()
    try:
        # Generate without streaming
        response = model_mgr.generate_text(
            prompt=simple_prompt,
            max_tokens=50,
            temperature=0.7,
            top_p=0.9,
            stream=False
        )
        gen_time = time.time() - gen_start

        print(f"\n[SUCCESS] Generation completed in {gen_time:.2f}s")
        print(f"Response: {response}")
        print(f"Response length: {len(response)} chars")

    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Legal document snippet (non-streaming)
    print("\n" + "-"*70)
    print("TEST 2: Legal document snippet (non-streaming)")
    print("-"*70)

    legal_prompt = """Summarize the following legal document:

PLAINTIFF: John Smith
DEFENDANT: ABC Corporation
CLAIM: Employment discrimination
DATE: January 15, 2022
COURT: State District Court

The plaintiff alleges that the defendant terminated his employment based on age discrimination.

Summary:"""

    print(f"\nPrompt length: {len(legal_prompt)} chars")
    print("\nGenerating response (non-streaming)...")

    gen_start = time.time()
    try:
        response = model_mgr.generate_text(
            prompt=legal_prompt,
            max_tokens=100,
            temperature=0.5,
            top_p=0.9,
            stream=False
        )
        gen_time = time.time() - gen_start

        print(f"\n[SUCCESS] Generation completed in {gen_time:.2f}s")
        print(f"Response:\n{response}")
        print(f"Response length: {len(response)} chars")

    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: With proper chat format (non-streaming)
    print("\n" + "-"*70)
    print("TEST 3: Phi-3 chat format (non-streaming)")
    print("-"*70)

    chat_prompt = """<|system|>
You are a helpful legal assistant. Summarize documents clearly and concisely.
<|end|>
<|user|>
Summarize: A contract between Company A and Company B for software services.
<|end|>
<|assistant|>"""

    print(f"\nPrompt length: {len(chat_prompt)} chars")
    print("\nGenerating response (non-streaming)...")

    gen_start = time.time()
    try:
        response = model_mgr.generate_text(
            prompt=chat_prompt,
            max_tokens=100,
            temperature=0.7,
            top_p=0.9,
            stream=False
        )
        gen_time = time.time() - gen_start

        print(f"\n[SUCCESS] Generation completed in {gen_time:.2f}s")
        print(f"Response:\n{response}")
        print(f"Response length: {len(response)} chars")

    except Exception as e:
        print(f"[ERROR] Generation failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*70)
    print("TESTS COMPLETE")
    print("="*70)

if __name__ == '__main__':
    test_simple_inference()
