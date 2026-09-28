#!/usr/bin/env python3
"""
wade_server.py
----------------
Wade's backend. This is the only piece that talks to the model, the
filesystem, and the network — wade_index.html never touches any of those
directly, it only calls this server.

Usage:
    python3 wade_server.py
or, better, just run wade_start.sh — it installs dependencies, brings the
model server up, starts this, and opens your browser for you.
"""

import os
import json
import time
import threading
import subprocess
from pathlib import Path

from flask import Flask, request, jsonify, Response
import requests

import wade_security as sec

# ---------------------------------------------------------------------------
# Configuration — every value below can be overridden with an env var of the
# same name, so you never have to edit this file to point Wade at your setup.
#
# WADE_BACKEND picks how Wade talks to the model:
#   "ollama"   — you run models with `ollama run <name>` (e.g. llama3.2:3b).
#                This is the default, since it's the most common local setup.
#   "llamacpp" — you run a raw .gguf file yourself with llama.cpp's llama-server.
# ---------------------------------------------------------------------------
WADE_PORT = int(os.environ.get("WADE_PORT", 7860))
BACKEND_KIND = os.environ.get("WADE_BACKEND", "ollama").strip().lower()
LLAMA_HOST = os.environ.get("WADE_LLAMA_HOST", "127.0.0.1")
LLAMA_PORT = int(os.environ.get("WADE_LLAMA_PORT", 11434 if BACKEND_KIND == "ollama" else 8080))
LLAMA_URL = f"http://{LLAMA_HOST}:{LLAMA_PORT}"
LLAMA_BIN = os.environ.get("WADE_LLAMA_BIN", "ollama" if BACKEND_KIND == "ollama" else "llama-server")
MODEL_NAME = os.environ.get("WADE_MODEL_NAME", "llama3.2:3b")  # the model Ollama should use
MODEL_PATH = os.environ.get("WADE_MODEL_PATH", "")  # llamacpp mode only: path to your .gguf file
AUTO_START_BACKEND = os.environ.get("WADE_AUTOSTART", "1") != "0"

BASE_DIR = Path(__file__).resolve().parent
INDEX_FILE = BASE_DIR / "wade_index.html"

app = Flask(__name__)
_backend_process = None
_backend_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Model backend lifecycle — "the AI should run automatically"
# ---------------------------------------------------------------------------
def backend_alive() -> bool:
    try:
        if BACKEND_KIND == "ollama":
            r = requests.get(f"{LLAMA_URL}/api/tags", timeout=1.5)  # Ollama's own health check
        else:
            r = requests.get(f"{LLAMA_URL}/health", timeout=1.5)  # llama.cpp's llama-server
        return r.status_code == 200
    except requests.RequestException:
        return False


def start_backend_if_needed() -> bool:
    """
    Brings the local model server up on its own if it isn't already running.
    Ollama on Windows/Mac usually already runs in the background after install,
    so this is mainly a fallback for when it's been quit or hasn't started yet.
    """
    global _backend_process
    with _backend_lock:
        if backend_alive():
            return True
        if not AUTO_START_BACKEND:
            return False
        try:
            if BACKEND_KIND == "ollama":
                _backend_process = subprocess.Popen(
                    [LLAMA_BIN, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                if not MODEL_PATH:
                    sec.log_event("backend_autostart_skipped", {"reason": "WADE_MODEL_PATH not set"})
                    return False
                _backend_process = subprocess.Popen(
                    [LLAMA_BIN, "-m", MODEL_PATH, "--port", str(LLAMA_PORT), "--host", LLAMA_HOST],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except FileNotFoundError:
            sec.log_event("backend_autostart_failed", {"reason": f"'{LLAMA_BIN}' not found on PATH"})
            return False
        for _ in range(30):  # give it up to ~30s to warm up
            if backend_alive():
                sec.log_event("backend_autostarted", {"pid": _backend_process.pid})
                return True
            time.sleep(1)
        sec.log_event("backend_autostart_timeout", {})
        return False


# ---------------------------------------------------------------------------
# The page — token is injected here, never typed or pasted by hand
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    token = sec.get_or_create_token()
    html = INDEX_FILE.read_text(encoding="utf-8")
    html = html.replace("__WADE_TOKEN__", token)
    return Response(html, mimetype="text/html")


@app.route("/api/status")
@sec.require_token
def status():
    alive = backend_alive() or start_backend_if_needed()
    return jsonify({"backend_alive": alive, "workspace": str(sec.WORKSPACE_DIR)})


# ---------------------------------------------------------------------------
# Chat — the model can call tools, but every single call still needs a human
# "Allow" before it runs. This endpoint never executes a tool itself; it only
# ever tells the client what the model is asking for.
# ---------------------------------------------------------------------------
LANG_SYSTEM_PROMPTS = {
    "en": "You are Wade, a private local assistant running entirely on the user's own device. Reply in clear English.",
    "ta": "நீ Wade, பயனரின் சொந்த சாதனத்தில் மட்டும் இயங்கும் தனிப்பட்ட உதவியாளர். எப்போதும் தமிழில் பதில் அளி.",
    "auto": (
        "You are Wade, a private local assistant running entirely on the user's own device. "
        "The user may write in Tamil, English, or a mix of both (Tanglish). Reply in whichever "
        "of Tamil or English they just used; if they mixed both, you may mix too."
    ),
}

TOOL_HINT = (
    " You have four tools: list_files, read_file, write_file, and delete_file, scoped to the "
    "user's Wade workspace folder. Use them whenever they'd help answer the user instead of "
    "asking the user to paste file content in. delete_file is permanent — only call it when the "
    "user has clearly asked for that file to be deleted, not as a side effect of something else. "
    "Every call you make first has to be approved by the user, so a result may come back as "
    "'permission denied' — if it does, tell the user plainly rather than silently retrying."
)

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List the files and folders at a path inside the user's Wade workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path inside the workspace, e.g. '.' for the top level."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the text content of a file inside the user's Wade workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file inside the workspace."}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file inside the user's Wade workspace with given text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file inside the workspace."},
                    "content": {"type": "string", "description": "The full text content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Permanently delete a single file inside the user's Wade workspace. Cannot delete folders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative path to the file inside the workspace."}
                },
                "required": ["path"],
            },
        },
    },
]

MAX_HISTORY_MESSAGES = 40  # generous cap so a multi-step tool exchange doesn't get truncated mid-loop


def _tool_to_action(name: str, args: dict):
    """Maps a tool call to the (permission action, relative path) wade_security understands."""
    path = str((args or {}).get("path", ""))
    if name == "list_files":
        return "list", path
    if name == "read_file":
        return "read", path
    if name == "write_file":
        return "write", path
    if name == "delete_file":
        return "delete", path
    return None, path


def _call_model(messages: list) -> dict:
    """One non-streaming round-trip to the backend. Returns the assistant message dict."""
    r = requests.post(
        f"{LLAMA_URL}/v1/chat/completions",
        json={"model": MODEL_NAME, "messages": messages, "tools": TOOLS, "temperature": 0.7},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]


@app.route("/api/chat/step", methods=["POST"])
@sec.require_token
@sec.chat_rate_limited
def chat_step():
    """
    One step of a conversation. The client owns the full message history (this
    server keeps no session state) and calls this repeatedly: once for the
    user's new message, then again after each tool result, until it gets back
    type "final".
    """
    body = request.get_json(force=True, silent=True) or {}
    incoming = body.get("messages")
    lang = body.get("lang", "auto")

    if not isinstance(incoming, list) or not incoming:
        return jsonify({"error": "messages array required"}), 400
    if len(json.dumps(incoming)) > 200_000:
        return jsonify({"error": "conversation got too long — start a new chat"}), 400
    if not backend_alive() and not start_backend_if_needed():
        return jsonify({"error": "the model isn't running — check the Wade server window"}), 503

    system = {"role": "system", "content": LANG_SYSTEM_PROMPTS.get(lang, LANG_SYSTEM_PROMPTS["auto"]) + TOOL_HINT}
    messages = [system] + incoming[-MAX_HISTORY_MESSAGES:]

    try:
        assistant_msg = _call_model(messages)
    except requests.RequestException as e:
        return jsonify({"error": f"lost connection to the model: {e}"}), 502
    except (KeyError, IndexError, ValueError):
        return jsonify({"error": "the model returned something Wade couldn't parse"}), 502

    tool_calls = assistant_msg.get("tool_calls") or []
    if not tool_calls:
        return jsonify({"type": "final", "message": {"role": "assistant", "content": assistant_msg.get("content") or ""}})

    pending = []
    for tc in tool_calls:
        fn = (tc or {}).get("function") or {}
        name = fn.get("name", "")
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except json.JSONDecodeError:
            args = {}
        action, rel_path = _tool_to_action(name, args)
        pending.append({
            "id": tc.get("id") or f"call_{len(pending)}",
            "name": name,
            "args": args,
            "action": action,
            "path": rel_path,
            "already_granted": bool(action) and sec.is_granted(rel_path, action),
        })

    return jsonify({"type": "tool_call", "assistant_message": assistant_msg, "pending": pending})


@app.route("/api/tools/execute", methods=["POST"])
@sec.require_token
@sec.file_rate_limited
def tools_execute():
    """
    Executes exactly one tool call the model asked for — and only after the
    human has clicked Allow for it. decision="deny" (or missing) never
    touches the filesystem; it just reports the denial back as a result so
    the model can tell the user.
    """
    body = request.get_json(force=True, silent=True) or {}
    call_id = body.get("id", "")
    name = body.get("name", "")
    args = body.get("args") or {}
    decision = body.get("decision", "deny")
    remember = bool(body.get("remember", False))

    action, rel_path = _tool_to_action(name, args)
    if action is None:
        return jsonify({"id": call_id, "result": f"error: '{name}' is not a tool Wade has"})

    if decision != "allow":
        sec.log_event("ai_tool_denied", {"tool": name, "path": rel_path, "action": action})
        return jsonify({"id": call_id, "result": f"permission denied by the user for {action} on '{rel_path}'"})

    sec.grant(rel_path, action, remember=remember)
    try:
        if name == "list_files":
            result = json.dumps({"path": rel_path, "entries": sec.guarded_list(rel_path)})
        elif name == "read_file":
            result = sec.guarded_read(rel_path)[:8000]
        elif name == "write_file":
            sec.guarded_write(rel_path, str(args.get("content", "")))
            result = f"wrote {len(str(args.get('content', '')))} bytes to '{rel_path}'"
        elif name == "delete_file":
            sec.guarded_delete(rel_path)
            result = f"deleted '{rel_path}'"
        else:
            result = f"error: '{name}' is not a tool Wade has"
    except sec.PermissionDenied as e:
        result = f"error: {e}"
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        result = f"error: '{rel_path}' not found or not a deletable file"

    return jsonify({"id": call_id, "result": result})


# ---------------------------------------------------------------------------
# Files — permission-gated on every single call, see wade_security.py
# ---------------------------------------------------------------------------
def _permission_response(err: sec.PermissionDenied, rel: str, action: str):
    return jsonify({"error": str(err), "needs_permission": True, "path": rel, "action": action}), 403


@app.route("/api/files/list")
@sec.require_token
@sec.file_rate_limited
def files_list():
    rel = request.args.get("path", ".")
    try:
        return jsonify({"path": rel, "entries": sec.guarded_list(rel)})
    except sec.PermissionDenied as e:
        return _permission_response(e, rel, "list")
    except (FileNotFoundError, NotADirectoryError):
        return jsonify({"error": f"'{rel}' is not a directory"}), 404


@app.route("/api/files/read")
@sec.require_token
@sec.file_rate_limited
def files_read():
    rel = request.args.get("path", "")
    try:
        return jsonify({"path": rel, "content": sec.guarded_read(rel)})
    except sec.PermissionDenied as e:
        return _permission_response(e, rel, "read")
    except FileNotFoundError:
        return jsonify({"error": f"'{rel}' not found"}), 404


@app.route("/api/files/write", methods=["POST"])
@sec.require_token
@sec.file_rate_limited
def files_write():
    body = request.get_json(force=True, silent=True) or {}
    rel = body.get("path", "")
    content = body.get("content", "")
    try:
        sec.guarded_write(rel, content)
        return jsonify({"ok": True})
    except sec.PermissionDenied as e:
        return _permission_response(e, rel, "write")


@app.route("/api/files/grant", methods=["POST"])
@sec.require_token
def files_grant():
    """Only ever called right after a human clicks Allow in the permission dialog."""
    body = request.get_json(force=True, silent=True) or {}
    rel = body.get("path", "")
    action = body.get("action", "")
    remember = bool(body.get("remember", False))
    if action not in ("read", "write", "list", "delete"):
        return jsonify({"error": "invalid action"}), 400
    sec.grant(rel, action, remember=remember)
    return jsonify({"ok": True})


@app.route("/api/files/revoke-all", methods=["POST"])
@sec.require_token
def files_revoke_all():
    sec.revoke_all()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Wade token (saved to {sec.TOKEN_FILE}, injected into the page automatically)")
    print(f"Workspace (the only folder Wade can ever touch): {sec.WORKSPACE_DIR}")
    print(f"Backend: {BACKEND_KIND} at {LLAMA_URL}, model: {MODEL_NAME if BACKEND_KIND == 'ollama' else MODEL_PATH}")
    if AUTO_START_BACKEND:
        threading.Thread(target=start_backend_if_needed, daemon=True).start()
    else:
        print("WADE_AUTOSTART=0 — start your model server yourself before chatting.")
    print(f"Open http://127.0.0.1:{WADE_PORT} — the page signs itself in automatically.")
    app.run(host="0.0.0.0", port=WADE_PORT, threaded=True)
