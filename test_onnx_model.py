"""
Test script for ONNX Model Manager
Verifies that Phi-3 ONNX model loads and generates text with DirectML acceleration.
"""

import time
import sys

# Add src to path
sys.path.insert(0, '.')

from src.ai import ONNXModelManager

print("=" * 70)
print("ONNX Model Manager Test - Phi-3 with DirectML")
print("=" * 70)

# Initialize model manager
print("\n[1/4] Initializing ONNX Model Manager...")
manager = ONNXModelManager()

# Check available models
print("\n[2/4] Checking available models...")
models = manager.get_available_models()

for key, info in models.items():
    status = "[OK]" if info['available'] else "[NOT FOUND]"
    print(f"  {status} {info['name']}")
    print(f"        Path: {info['path']}")
    print(f"        Size: {info['size_gb']} GB")
    print()

# Load the standard DirectML model
print("[3/4] Loading Phi-3 DirectML model...")
print("      (This may take 10-30 seconds...)")
load_start = time.time()

success = manager.load_model('standard', verbose=False)

load_time = time.time() - load_start

if not success:
    print("\n[FAILED] Could not load model!")
    sys.exit(1)

print(f"\n[OK] Model loaded in {load_time:.2f} seconds")

# Test text generation with a legal summary
print("\n[4/4] Testing text generation...")
print("      Generating 100-word summary of sample legal text...")
print()

sample_text = """
SUPREME COURT OF THE STATE OF NEW YORK
Plaintiff SUPPLEMENTAL BILL OF PARTICULARS against ROBERT L. WIGHTON, M.D.

The plaintiff alleges medical malpractice occurred during a surgical procedure
performed on January 15, 2022. The defendant, Dr. Robert Wighton, allegedly
failed to properly diagnose and treat complications that arose during the surgery.
As a result of this negligence, the plaintiff suffered severe injuries including
permanent nerve damage and loss of mobility in the left arm.

The plaintiff is seeking compensatory damages in the amount of $500,000 for
medical expenses, lost wages, and pain and suffering.
"""

print("-" * 70)
print("STREAMING OUTPUT (watch tokens appear in real-time):")
print("-" * 70)

gen_start = time.time()
full_summary = ""
token_count = 0
first_token_time = None

try:
    for token in manager.generate_summary(sample_text, max_words=100, stream=True):
        if first_token_time is None:
            first_token_time = time.time() - gen_start
            print(f"\n[First token in {first_token_time:.2f}s]")
            print()

        print(token, end='', flush=True)
        full_summary += token
        token_count += 1

    gen_time = time.time() - gen_start

    print()
    print()
    print("-" * 70)
    print("GENERATION STATISTICS:")
    print("-" * 70)
    print(f"Total time: {gen_time:.2f} seconds")
    print(f"First token: {first_token_time:.2f} seconds")
    print(f"Tokens generated: {token_count}")
    print(f"Tokens/second: {token_count / gen_time:.2f}")
    print(f"Words in summary: {len(full_summary.split())}")
    print()

    # Performance expectations
    print("PERFORMANCE COMPARISON:")
    print(f"  ONNX DirectML:      {token_count / gen_time:.2f} tokens/sec (CURRENT)")
    print(f"  llama-cpp-python:   ~0.6 tokens/sec (OLD)")
    print(f"  Speedup:            {(token_count / gen_time) / 0.6:.1f}x faster")
    print()

    if token_count / gen_time < 2.0:
        print("[WARNING] Performance is lower than expected.")
        print("          Expected: 3-6 tokens/sec with DirectML")
        print("          DirectML may not be active. Check GPU driver.")
    else:
        print("[SUCCESS] Performance looks good! DirectML is working.")

except Exception as e:
    print(f"\n[ERROR] Generation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()
print("=" * 70)
print("Test Complete!")
print("=" * 70)
