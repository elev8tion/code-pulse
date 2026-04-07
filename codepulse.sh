#!/bin/bash
# Code-Pulse launcher — activates venv, starts the web server, and opens browser
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build frontend if dist doesn't exist yet
FRONTEND_DIST="$DIR/frontend/dist"
if [ ! -d "$FRONTEND_DIST" ]; then
  if command -v node &>/dev/null && [ -f "$DIR/frontend/package.json" ]; then
    echo "📦 Building frontend…"
    cd "$DIR/frontend"
    npm install --silent
    npm run build --silent
    cd "$DIR"
    echo "✅ Frontend built."
  else
    echo "⚠️  Node.js not found or frontend/package.json missing."
    echo "   The server will start, but the web UI will not be available."
    echo "   Install Node.js and run: cd frontend && npm install && npm run build"
  fi
fi

# Launch the Python server (which opens the browser)
exec "$DIR/.venv/bin/codepulse" "$@"
