"""
Quick test of Phi-3 Mini summary generation performance.
This test focuses on the key metric: How long to generate a summary?
"""

import time
from src.ai import ModelManager

print("=" * 60)
print("Phi-3 Mini Summary Generation Test")
print("=" * 60)

# Initialize model manager
print("\n1. Initializing ModelManager...")
mm = ModelManager()

# Check model availability
print("\n2. Checking model availability...")
models = mm.get_available_models()
print(f"   Standard (Phi-3): {models['standard']['available']}")
print(f"   Pro (Gemma 2): {models['pro']['available']}")

if not models['standard']['available']:
    print("   ERROR: Phi-3 model not found!")
    exit(1)

# Load Phi-3 model
print("\n3. Loading Phi-3 Mini 3.8B model...")
load_start = time.time()
success = mm.load_model('standard')
load_time = time.time() - load_start

if not success:
    print(f"   ERROR: Model failed to load!")
    exit(1)

print(f"   [OK] Model loaded in {load_time:.1f} seconds")

# Test with realistic legal text input (500 words)
print("\n4. Testing summary generation with 500-word legal text input")
test_legal_text = """
In the matter of Smith v. Jones Corporation, the plaintiff alleges that the defendant
engaged in fraudulent misrepresentation during contract negotiations. The parties entered
into a commercial lease agreement on March 15, 2023, for office space located at
123 Main Street. The plaintiff claims that the defendant made false representations
regarding the condition of the HVAC system and electrical infrastructure.

During negotiations, defendant's agent stated that all building systems had been recently
upgraded and inspected. However, upon taking possession, plaintiff discovered that the
HVAC system was over 20 years old and required immediate replacement at a cost of $45,000.
The electrical system also failed inspection, requiring $12,000 in repairs to meet code.

Plaintiff seeks damages of $57,000 for repair costs, plus $23,000 in consequential damages
for business interruption during the repair period. Defendant denies all allegations and
claims that the lease agreement contained an "as-is" clause disclaiming any warranties
regarding the condition of the premises. The defendant also argues that the plaintiff had
an opportunity to inspect the property before signing the lease.

The court must determine whether the defendant's pre-contractual statements constituted
actionable misrepresentation and whether the "as-is" clause effectively waived any such claims.
""" * 2  # Duplicate to get ~500 words

word_count = len(test_legal_text.split())
print(f"   Input: {word_count} words")
print(f"   Target summary: 100 words")
print(f"   Starting generation...")

# Generate summary with streaming
gen_start = time.time()
first_token_time = None
tokens = []

try:
    for token in mm.generate_summary(
        case_text=test_legal_text,
        max_words=100,
        stream=True
    ):
        if first_token_time is None:
            first_token_time = time.time() - gen_start
            print(f"   [!] First token after {first_token_time:.1f} seconds!")

        tokens.append(token)

        # Print progress every 20 tokens
        if len(tokens) % 20 == 0:
            elapsed = time.time() - gen_start
            print(f"   ... {len(tokens)} tokens ({elapsed:.1f}s elapsed)")

    total_time = time.time() - gen_start
    full_summary = ''.join(tokens)
    summary_words = len(full_summary.split())

    print(f"\n   [OK] SUCCESS!")
    print(f"   Total time: {total_time:.1f} seconds")
    print(f"   First token: {first_token_time:.1f} seconds")
    print(f"   Tokens generated: {len(tokens)}")
    print(f"   Summary length: {summary_words} words")
    print(f"   Tokens/second: {len(tokens)/total_time:.1f}")
    print(f"\n   Summary preview:")
    print(f"   {full_summary[:200]}...")

except Exception as e:
    print(f"   [ERROR] {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 60)
print("[OK] Test Complete!")
print(f"Phi-3 Mini Performance: {total_time:.1f}s for {word_count}-word input")
print("=" * 60)
