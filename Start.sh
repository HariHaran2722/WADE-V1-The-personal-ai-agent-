#!/usr/bin/env bash
# wade_start.sh
# The one thing you run (or double-click, if your file manager allows it)
# to bring Wade up: installs missing dependencies, starts the model backend
# and the web server, then opens your browser to the already-signed-in page.

set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# ---- edit these once for your machine, or export them before running ----
export WADE_BACKEND="${WADE_BACKEND:-ollama}"          # "ollama" or "llamacpp"
export WADE_MODEL_NAME="${WADE_MODEL_NAME:-llama3.2:3b}"  # used when WADE_BACKEND=ollama
export WADE_PORT="${WADE_PORT:-7860}"

# Only used when WADE_BACKEND=llamacpp — ignored otherwise:
# export WADE_MODEL_PATH="$HOME/models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
# export WADE_LLAMA_BIN="llama-server"
# ---------------------------------------------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found — install it first, then run this again."
  exit 1
fi

if ! python3 -c "import flask, requests" >/dev/null 2>&1; then
  echo "Installing Wade's Python dependencies (flask, requests)…"
  pip3 install --quiet flask requests
fi

BACKEND_BIN="${WADE_LLAMA_BIN:-$([ "$WADE_BACKEND" = "ollama" ] && echo ollama || echo llama-server)}"
if ! command -v "$BACKEND_BIN" >/dev/null 2>&1; then
  echo "Note: '$BACKEND_BIN' isn't on your PATH — Wade will start, but it won't"
  echo "be able to bring the model up on its own. Start it yourself (e.g. 'ollama serve'),"
  echo "or set WADE_LLAMA_BIN to the right path, then reload the page."
fi

echo "Starting Wade on http://127.0.0.1:${WADE_PORT}"
python3 wade_server.py &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null' EXIT

for _ in $(seq 1 20); do
  if curl -s "http://127.0.0.1:${WADE_PORT}" >/dev/null 2>&1; then break; fi
  sleep 0.5
done

URL="http://127.0.0.1:${WADE_PORT}"
if command -v notify-send >/dev/null 2>&1; then
  notify-send "Wade" "Ready at $URL" 2>/dev/null || true
fi
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 &
elif command -v termux-open-url >/dev/null 2>&1; then
  termux-open-url "$URL"
elif command -v open >/dev/null 2>&1; then
  open "$URL"
else
  echo "Open this in your browser: $URL"
fi

wait "$SERVER_PID"
