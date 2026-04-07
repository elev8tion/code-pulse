# Code-Pulse ⚡

> A local web-based visual studio for solo agentic programming with Claude Code.

Code-Pulse is your **coding heartbeat** — a browser-based dashboard that puts you in full visual command of Claude Code Pro running locally. It shows its work in real time, self-corrects, is transparent, and learns — letting you make the best directional choices while working solo.

---

## What It Is

Most AI coding tools are black boxes. You type a prompt, you get code back, and you have no idea what happened in between. Code-Pulse solves this by making everything **visible**:

- Which tools Claude is using right now (file reads, shell commands, web searches)
- Which subagent is active and what it knows about your codebase
- What changed, where, and why — with live diffs and a heatmap of your most-touched files
- What the system recommends doing next
- A direct conversation channel to ask questions mid-flow

It runs **100% locally** using your Claude Code Pro subscription. No API key, no cloud dependency.

---

## Prerequisites

- **Python 3.11+**
- **Claude Code CLI** installed: `npm install -g @anthropic-ai/claude-code`
- **Node.js 18+** (for building the frontend)
- A Claude Code Pro subscription (authenticated via `claude auth`)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/elev8tion/code-pulse.git
cd code-pulse

# 2. Create a virtual environment and install
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .

# 3. Build the frontend
cd frontend
npm install
npm run build
cd ..
```

---

## Running Code-Pulse

### Open a project

```bash
# From inside your project folder:
codepulse

# Or specify the path:
codepulse open /path/to/my-project

# Resume a previous session:
codepulse resume my-project-name
```

The browser will open automatically at `http://localhost:3000`.

### Using the launcher script

```bash
./codepulse.sh              # opens current directory
./codepulse.sh open <path>  # opens specific project
```

### Terminal-only commands (no UI needed)

```bash
codepulse list              # list all saved projects and sessions
codepulse export my-project # export session as markdown report
```

---

## The Dashboard — 6 Visual Zones

```
┌─────────────────────────────────────────────────────────────────────┐
│  ⚡ Code-Pulse  /path/to/project              2026-01-01 · Turn 5  │
├──────────────────┬─────────────────────────────────┬───────────────┤
│  🎛️ Arsenal      │  🎬 Orchestration                │  ⚡ Actions   │
│                  │                                 │               │
│  Visual tools    │  Agent slots + handoff history  │  Quick-fire   │
│  Claude is using │  (who's working, who knows what)│  action cards │
│  right now       │                                 │  + processes  │
│  (lights up!)    │                                 │               │
├──────────────────┼─────────────────────────────────┼───────────────┤
│  📊 Results      │  💬 Chat / Discussion            │  ➡️ Next Steps │
│                  │                                 │               │
│  Turn history    │  Main interaction area          │  Synopsis-    │
│  with synopses   │  Streaming Claude responses     │  derived      │
│  + codebase      │  Discussion mode for mid-flow   │  recommendations│
│  heatmap         │  adjustments                    │  + session    │
│                  │                                 │  status       │
└──────────────────┴─────────────────────────────────┴───────────────┘
```

### 🎛️ Arsenal / Tool Palette
Visual display of every tool Claude can use (Bash, Read, Write, Edit, Glob, Grep, WebFetch, etc.). When Claude calls a tool, its card **lights up in real time** via WebSocket events.

### 🎬 Orchestration View
Shows the rotating subagent pool (3 agents by default). Displays which agent is currently active, what each one knows (synopsis from their last turn), and the full handoff history so you can trace how context was passed.

### ⚡ Actions In Play
One-click action cards for common solo dev workflows: Fix Bugs, Write Tests, Scaffold Feature, Deploy, What's Next, Commit & Push, and more. Also shows detected project processes (npm scripts, Makefile targets, etc.) with start/stop controls.

### 📊 Results Timeline
Timestamped turn history showing what you asked, what changed, and the subagent's 3-bullet synopsis of why. Below that, a live heatmap of your codebase showing which files have been changed most intensely during the session.

### 💬 Chat / Discussion Panel
The main interaction area. Type prompts, see streaming responses. Toggle **Discussion Mode** to ask the current agent questions about recent changes without starting a new completion cycle — useful for "why did you do that?" or "is this the right approach?".

### ➡️ Next Steps / Status
Prominent display of recommendations extracted from the latest synopsis. Session info, turn count, streaming status, and an export button.

---

## The Philosophy

**Heartbeat** — Code-Pulse is always pulsing. The animated indicator in the header reflects whether the system is idle (slow pulse) or actively working (fast pulse). You always know it's alive.

**Transparency** — Every action Claude takes is surfaced. Tool calls light up in real time. Diffs show exactly what changed. Synopses explain why. You are never in the dark.

**Self-correction** — The rotating subagent pool carries forward a synopsis of what happened, what changed, and what to watch for. Each agent picks up where the last left off, maintaining context across turns.

**Learning** — The heatmap accumulates across the session, showing you which parts of your codebase are getting the most attention. Over time, patterns emerge.

---

## Architecture

```
codepulse/
├── server.py           ← FastAPI + WebSocket server (NEW)
├── agents/             ← SubAgentPool, SubAgent, DiscussionSession
├── api/                ← DispatchClient (spawns claude CLI)
├── git/                ← DiffTracker, UnifiedDiffParser
├── heatmap/            ← HeatMapAggregator
├── session/            ← SessionManager, MarkdownExporter
├── process/            ← ProjectDetector, ProcessRunner
├── ncb/                ← NCBSync (cloud backup)
├── utils/              ← paths, time_utils
└── config.py

frontend/               ← React + Vite web UI (NEW)
├── src/
│   ├── App.tsx         ← Main dashboard layout
│   ├── panels/         ← ArsenalPanel, OrchestrationPanel, ActionsPanel,
│   │                      ResultsPanel, ChatPanel, NextStepsPanel
│   ├── components/     ← Heartbeat
│   └── hooks/          ← useWebSocket
└── package.json
```

The FastAPI server (`server.py`) is the bridge between the existing Python backend modules and the new web frontend. It:
- Manages all backend objects (DispatchClient, SubAgentPool, etc.) for the lifetime of the server process
- Streams Claude responses to the browser in real time via WebSocket
- Exposes REST endpoints for all user actions
- Serves the built frontend static files

---

## Development

To run with live reload (frontend changes reflect immediately without rebuilding):

```bash
# Terminal 1: start the backend
CODEPULSE_PROJECT_PATH=/your/project uvicorn codepulse.server:app --host 0.0.0.0 --port 3000 --reload

# Terminal 2: start the frontend dev server (proxies /api and /ws to localhost:3000)
cd frontend
npm run dev
# Open http://localhost:5173
```

---

## Contributing

Code-Pulse is a solo dev tool built for transparency and clarity. Contributions that improve the visual experience, add useful quick actions, or improve the backend robustness are welcome. Open an issue first to discuss significant changes.

---

*Built with ❤️ for solo devs who want to see exactly what their AI partner is doing.*
