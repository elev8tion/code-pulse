"""App-wide constants and configuration."""
from pathlib import Path

# Claude model for main completions (passed to claude --model)
CLAUDE_MODEL = "claude-opus-4-6"

# Lighter model for subagent synopsis
SYNOPSIS_MODEL = "claude-haiku-4-5-20251001"

# Subagent pool size
AGENT_POOL_SIZE = 3

# How many messages to keep in each subagent's context window
AGENT_CONTEXT_WINDOW = 6

# Storage root
CODEPULSE_HOME = Path.home() / ".codepulse"
PROJECTS_DIR = CODEPULSE_HOME / "projects"

# Quick Actions customization file
ACTIONS_FILE = CODEPULSE_HOME / "actions.json"

# Where GitHub repos are cloned to
CLONES_DIR = Path.home() / "codepulse-projects"

# Process Manager
MAX_PROCESS_OUTPUT_LINES = 200
PROCESS_STOP_TIMEOUT_SECS = 3.0

# Diff animation delay between entries (seconds)
DIFF_ANIMATION_DELAY = 0.12
