#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="$(dirname "$0")/.venv"

# mcp requires Python 3.10+; prefer Homebrew python3 over the macOS system stub
PYTHON=$(command -v /opt/homebrew/bin/python3 || command -v python3)

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

echo "Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$(dirname "$0")/requirements.txt"

echo "Starting R2D2 MCP server..."
exec "$VENV_DIR/bin/python" "$(dirname "$0")/R2D2-mcp.py"
