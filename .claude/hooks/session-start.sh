#!/bin/bash
set -euo pipefail

# Exit immediately on Windows - environment is already set up locally
# This hook is only needed for Claude Code in browser (Linux environment)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
  exit 0
fi

# Also exit if not in remote environment (just in case)
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# If we get here, we're in the browser-based Linux environment
PLATFORM="linux"
PYTHON_BIN="venv/bin/python"
PIP_BIN="venv/bin/pip"

echo "🔧 Setting up Python environment for CaseSummarizer..."
echo "   Platform detected: $PLATFORM"

# Navigate to project directory if CLAUDE_PROJECT_DIR is set
if [ -n "${CLAUDE_PROJECT_DIR:-}" ]; then
  cd "$CLAUDE_PROJECT_DIR"
fi

# Install system dependencies (Tesseract OCR)
echo "📦 Installing system dependencies..."
if ! command -v tesseract &> /dev/null; then
  apt-get install -y -qq tesseract-ocr > /dev/null 2>&1
  echo "   ✅ Tesseract OCR installed"
else
  echo "   ✅ Tesseract OCR already available"
fi

# Determine Python command (Linux)
PYTHON_CMD="python3"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
  echo "📦 Creating virtual environment..."
  $PYTHON_CMD -m venv venv
else
  echo "✅ Virtual environment already exists"
fi

# Check if venv was created successfully
if [ ! -f "$PYTHON_BIN" ]; then
  echo "❌ Error: Virtual environment not properly created"
  exit 1
fi

# Install dependencies
echo "📥 Installing Python dependencies..."
"$PIP_BIN" install --quiet --upgrade pip
"$PIP_BIN" install --quiet -r requirements.txt

# Download NLTK data
echo "📚 Downloading NLTK data..."
"$PYTHON_BIN" -c "import nltk; nltk.download('words', quiet=True)"

# Set Python path and pytest options for the session (if CLAUDE_ENV_FILE exists)
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PYTHONPATH=\"\$CLAUDE_PROJECT_DIR\"" >> "$CLAUDE_ENV_FILE"
  echo "export PYTEST_ADDOPTS=\"-p no:pytest-qt\"" >> "$CLAUDE_ENV_FILE"
fi

echo "✅ Environment setup complete!"
echo "   Python: $("$PYTHON_BIN" --version)"
echo "   Pip: $("$PIP_BIN" --version | head -n1)"
echo ""
echo "Ready to run tests with: venv/bin/pytest tests/ -v"
echo "Note: pytest-qt plugin is disabled in headless environment"
