#!/bin/bash
set -euo pipefail

# Only run in Claude Code remote environment (web browser)
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "🔧 Setting up Python environment for LocalScribe..."

# Navigate to project directory
cd "$CLAUDE_PROJECT_DIR"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv venv
else
  echo "✅ Virtual environment already exists"
fi

# Install dependencies
echo "📥 Installing Python dependencies..."
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet -r requirements.txt

# Download NLTK data
echo "📚 Downloading NLTK data..."
venv/bin/python -c "import nltk; nltk.download('words', quiet=True)"

# Set Python path and pytest options for the session
echo "export PYTHONPATH=\"\$CLAUDE_PROJECT_DIR\"" >> "$CLAUDE_ENV_FILE"
echo "export PYTEST_ADDOPTS=\"-p no:pytest-qt\"" >> "$CLAUDE_ENV_FILE"

echo "✅ Environment setup complete!"
echo "   Python: $(venv/bin/python --version)"
echo "   Pip: $(venv/bin/pip --version | head -n1)"
echo ""
echo "Ready to run tests with: venv/bin/pytest tests/ -v"
echo "Note: pytest-qt plugin is disabled in headless environment"
