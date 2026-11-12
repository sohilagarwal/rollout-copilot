#!/bin/bash
# Starts the rollout MCP server. On first run it creates .venv and installs the
# one package it needs, so it works the same on your Mac and in Claude Code on the web.
# Anything printed here goes to stderr: stdout is reserved for the MCP connection.
cd "$(dirname "$0")/.." || exit 1

if ! .venv/bin/python -c "import mcp" 2>/dev/null; then
  if command -v uv >/dev/null 2>&1; then
    uv venv -q --python ">=3.10" .venv >&2 && uv pip install -q --python .venv/bin/python -r requirements.txt >&2
  else
    python3 -m venv .venv >&2 && .venv/bin/pip install -q -r requirements.txt >&2
  fi
fi

[ "$1" = "--setup-only" ] && exit 0
exec .venv/bin/python server/rollout_server.py
