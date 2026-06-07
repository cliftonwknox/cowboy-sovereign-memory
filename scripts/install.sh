#!/usr/bin/env bash
# Cowboy Claude's Sovereign Memory — installer.
# OS-aware, tier-aware, chatty, and safe. Does the env + store; guides the model + wiring
# steps (those need the human's choices/paths). Run from anywhere.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OS="$(uname -s)"
PY="${PYTHON:-python3}"

echo "=================================================="
echo " Cowboy Claude's Sovereign Memory — install"
echo " OS: $OS   Root: $ROOT"
echo "=================================================="

# --- 1. virtualenv + deps ---
echo "[1/4] Python venv + dependencies…"
"$PY" -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install -q --upgrade pip
"$ROOT/.venv/bin/pip" install -q -r "$ROOT/requirements.txt"
echo "      ok"

# --- 2. initialize the store (sqlite-vec default) ---
echo "[2/4] Initializing the store…"
( cd "$ROOT" && CCSM_STORE="${CCSM_STORE:-sqlite}" "$ROOT/.venv/bin/python" - <<'PY'
from memory.config import load
from memory.store import open_store
s = open_store(load()); s.init_schema(); s.close()
print("      store schema initialized (backend:", load().store_backend + ")")
PY
)

# --- 3. model guidance (download + serve are the human's call) ---
echo "[3/4] Models:"
echo "      • Embedder (required): download a small GGUF (e.g. bge-small-en-v1.5 q8) and serve it:"
echo "          llama-server -m bge-small-en-v1.5.gguf --embedding --port 8900"
echo "        macOS uses Metal automatically; Linux uses CUDA if built with it, else CPU."
echo "      • Dreamer (Standard/Full only): serve a 2B or 4B chat GGUF and set:"
echo "          export CCSM_DREAMER_URL=http://127.0.0.1:8901"
echo "        Leave CCSM_DREAMER_URL unset for the Lite tier (no cognition)."

# --- 4. next steps (Claude does these with the human) ---
echo "[4/4] Wire Claude Code (the cowboy-sovereign-memory skill walks you through these):"
echo "      • Add recall + extraction hooks to ~/.claude/settings.json (paths under $ROOT)."
echo "      • Register MCP tools:"
echo "          claude mcp add cowboy-memory -- $ROOT/.venv/bin/python -m memory.mcp_tools"
echo "      • Schedule nightly sleep — see scripts/scheduler/ (systemd / launchd / cron)."
echo "      • Verify, then RESTART Claude Code so the hooks load."
echo ""
echo "Done. It's empty and local — your memory, your machine. 🤠"
