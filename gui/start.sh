#!/bin/bash
# Starts the Rollout Copilot web GUI on http://localhost:8000 (pass --port to change it).
# Reuses the server's .venv, creating it on first run.
cd "$(dirname "$0")/.." || exit 1
bash server/start.sh --setup-only || exit 1
exec .venv/bin/python gui/app.py "$@"
