import spacy
import sys
from pathlib import Path

try:
    # Adjust sys.path for local src imports if needed (though spacy.load doesn't rely on it)
    project_root = Path(__file__).parent
    if str(project_root.parent) not in sys.path:
        sys.path.insert(0, str(project_root.parent))

    print("Attempting to load spaCy model...")
    nlp = spacy.load("en_core_web_sm")
    print("spaCy model 'en_core_web_sm' loaded successfully!")

except Exception as e:
    print(f"Error loading spaCy model: {e}")
    sys.exit(1)

sys.exit(0)
