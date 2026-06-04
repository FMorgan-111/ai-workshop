# AI Workshop

Multi-terminal web workspace for AI Agents — **Hermes**, **Claude Code**, and **Codex** in one drag-resizable UI.

```bash
pip install websockets
python3 server.py
# Open http://localhost:8765
```

## Architecture

```
┌───────── Browser (index.html) ─────────┐
│                                         │
│  ┌─────────┬──────────────────────────┐ │
│  │         │  ○ Claude Code           │ │
│  │  ⎔      ├──────────────────────────┤ │
│  │ Hermes  │  ◇ Codex                 │ │
│  │         │                          │ │
│  └─────────┴──────────────────────────┘ │
│           ↕ WebSocket (port 8765)       │
└─────────────────────────────────────────┘
           ↕ PTY processes
┌─────────────────────────────────────────┐
│  Python Server (server.py)              │
│  ┌──────────┬──────────┬──────────────┐ │
│  │  bash    │  claude  │   codex      │ │
│  └──────────┴──────────┴──────────────┘ │
└─────────────────────────────────────────┘
```

- **Backend**: Python `websockets` + `pty` — one process per channel
- **Frontend**: xterm.js + WebSocket — 3 panels with draggable divider
- **Channels**: `hermes` (bash), `cc` (claude), `codex` (codex)

## Quick Start

```bash
# Install
pip install websockets

# Start server
python3 server.py

# Open browser
open http://localhost:8765
```

## Docker

```bash
docker build -t ai-workshop .
docker run -p 8765:8765 -it ai-workshop
```

## Channels

| Channel | Process | Purpose |
|---------|---------|---------|
| `hermes` | bash | Shell commands |
| `cc` | claude | Claude Code |
| `codex` | codex | OpenAI Codex |
