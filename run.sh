#!/bin/bash
# This script starts the FastAPI application using the correct Uvicorn syntax.
cd /mydata/python/ElysiaGameImmortal
# Load environment variables from .env file if it exists
if [ -f backend/.env ]; then
  # Convert CRLF to LF for cross-platform compatibility
  # This prevents issues when .env is edited on Windows and run on Linux/macOS
  sed -i 's/\r$//' backend/.env
  # Using a safer method to export variables
  set -o allexport
  source backend/.env
  set +o allexport
fi

# Use environment variables for host and port, with defaults
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-8000}

RELOAD_FLAG=""
# Check for 'true' in a case-insensitive way
if [[ "${UVICORN_RELOAD,,}" == "true" ]]; then
    RELOAD_FLAG="--reload"
fi

echo "Attempting to start server on ${HOST}:${PORT} with reload flag: '${RELOAD_FLAG}'"

# The command 'uv run uvicorn' is equivalent to 'uv uvicorn'.
# The key is the 'backend.app.main:app' part, which specifies the app instance.
/root/.local/bin/uv run python -m uvicorn backend.app.main:app --host ${HOST} --port ${PORT} ${RELOAD_FLAG}