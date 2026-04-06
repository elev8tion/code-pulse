#!/usr/bin/env bash
# CodePulse menu bar installer
# Installs the ⚡ menu bar app and registers it as a macOS Login Item.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_ROOT/.venv/bin/python"
MENUBAR_SCRIPT="$PROJECT_ROOT/codepulse/menubar.py"
PLIST="$HOME/Library/LaunchAgents/com.codepulse.menubar.plist"
LOG_DIR="$HOME/.codepulse/logs"

echo "⚡ CodePulse Menu Bar Installer"
echo "  Project: $PROJECT_ROOT"
echo ""

# ── 1. Check venv ────────────────────────────────────────────────────────────
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "Error: venv not found at $PROJECT_ROOT/.venv"
    echo "Run: python3 -m venv .venv && .venv/bin/pip install -e .[menubar]"
    exit 1
fi

# ── 2. Install rumps if missing ──────────────────────────────────────────────
if ! "$VENV_PYTHON" -c "import rumps" 2>/dev/null; then
    echo "Installing rumps..."
    "$PROJECT_ROOT/.venv/bin/pip" install "rumps>=0.4.0" --quiet
fi

# ── 3. Create log directory ──────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── 4. Write LaunchAgent plist ───────────────────────────────────────────────
cat > "$PLIST" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.codepulse.menubar</string>

    <key>ProgramArguments</key>
    <array>
        <string>${VENV_PYTHON}</string>
        <string>${MENUBAR_SCRIPT}</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>${LOG_DIR}/menubar.log</string>

    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/menubar.err</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
PLIST_EOF

echo "  Wrote: $PLIST"

# ── 5. Load the agent (starts it now) ───────────────────────────────────────
# Unload first in case it's already registered
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo ""
echo "✓ Menu bar app installed and running!"
echo "  ⚡ appears in your macOS menu bar."
echo "  It will auto-start on every login."
echo ""
echo "To uninstall:"
echo "  launchctl unload $PLIST && rm $PLIST"
