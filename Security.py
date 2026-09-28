"""
wade_security.py
------------------
Everything security-related for Wade lives in this one file, separate from
the server logic, so it's easy to audit on its own.

What it does:
  1. Generates and stores a session token — wade_server.py injects this into
     wade_index.html automatically, so you never copy/paste it by hand.
  2. Verifies that token on every API request (require_token).
  3. Rate-limits requests so nothing can hammer the local model or disk.
  4. Guards every single file access. Wade can only ever see one folder
     (~/wade_workspace), and by default EVERY read/write/listing needs an
     explicit "Allow" click in the UI — even for a file it already touched.
     The one exception is if you tick "remember this" in the permission
     dialog, which is the only way an access becomes standing.
  5. Keeps a plain-text audit log of every security-relevant event.

Nothing here reaches the network. This file only decides what wade_server.py
is allowed to do, not how it does it.
"""

import os
import time
import json
import secrets
import hashlib
import functools
from pathlib import Path
from collections import defaultdict, deque

from flask import request, jsonify

# ---------------------------------------------------------------------------
# Where Wade is allowed to keep state
# ---------------------------------------------------------------------------
WADE_HOME = Path.home() / ".wade"
WADE_HOME.mkdir(parents=True, exist_ok=True)

TOKEN_FILE = WADE_HOME / "token.txt"
AUDIT_LOG = WADE_HOME / "audit.log"
PERMISSIONS_FILE = WADE_HOME / "permissions.json"

# The ONLY folder Wade is ever allowed to read or write.
# If you change this, keep it a specific folder — never widen it to "/" or "~".
WORKSPACE_DIR = Path.home() / "wade_workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Token — generated once, injected into the page automatically
# ---------------------------------------------------------------------------
def get_or_create_token() -> str:
    if TOKEN_FILE.exists():
        existing = TOKEN_FILE.read_text().strip()
        if existing:
            return existing
    return _new_token()


def rotate_token() -> str:
    """Invalidates the old token immediately. Reload the page after calling this."""
    return _new_token()


def _new_token() -> str:
    token = secrets.token_hex(24)  # 192 bits
    TOKEN_FILE.write_text(token)
    try:
        os.chmod(TOKEN_FILE, 0o600)  # owner-only, on systems that support it
    except OSError:
        pass
    return token


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Auth decorator — every /api/* route in wade_server.py wears this
# ---------------------------------------------------------------------------
def require_token(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        current = get_or_create_token()
        supplied = request.headers.get("X-Wade-Token", "")
        if not supplied or _fingerprint(supplied) != _fingerprint(current):
            log_event("auth_rejected", {"path": request.path, "ip": request.remote_addr})
            return jsonify({"error": "invalid or missing token"}), 401
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Rate limiting — simple in-memory sliding window, per IP
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.time()
        q = self._hits[key]
        while q and now - q[0] > self.window_seconds:
            q.popleft()
        if len(q) >= self.max_requests:
            return False
        q.append(now)
        return True


_chat_limiter = RateLimiter(max_requests=30, window_seconds=60)
_file_limiter = RateLimiter(max_requests=60, window_seconds=60)


def _rate_limited(limiter: RateLimiter):
    def deco(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            key = request.remote_addr or "unknown"
            if not limiter.allow(key):
                log_event("rate_limited", {"path": request.path, "ip": key})
                return jsonify({"error": "too many requests — slow down a moment"}), 429
            return view(*args, **kwargs)
        return wrapped
    return deco


def chat_rate_limited(view):
    return _rate_limited(_chat_limiter)(view)


def file_rate_limited(view):
    return _rate_limited(_file_limiter)(view)


# ---------------------------------------------------------------------------
# File access — every access needs an explicit grant, one-time by default
# ---------------------------------------------------------------------------
class PermissionDenied(Exception):
    pass


_one_shot_grants = set()  # {(rel_path, action)} — consumed after a single use


def _load_grants() -> dict:
    if PERMISSIONS_FILE.exists():
        try:
            return json.loads(PERMISSIONS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_grants(grants: dict) -> None:
    PERMISSIONS_FILE.write_text(json.dumps(grants, indent=2))


def safe_path(rel_path: str) -> Path:
    """Resolves a requested path and guarantees it can't escape WORKSPACE_DIR."""
    root = WORKSPACE_DIR.resolve()
    candidate = (root / rel_path).resolve()
    if candidate != root and root not in candidate.parents:
        log_event("path_traversal_blocked", {"requested": rel_path})
        raise PermissionDenied(f"'{rel_path}' is outside Wade's workspace")
    return candidate


def is_granted(rel_path: str, action: str) -> bool:
    if (rel_path, action) in _one_shot_grants:
        return True
    entry = _load_grants().get(rel_path)
    return bool(entry and entry.get(action) is True)


def grant(rel_path: str, action: str, remember: bool = False) -> None:
    """
    Called only after a human clicks "Allow" in the UI — never automatically.
    remember=False (the default) allows exactly one access, then re-locks.
    remember=True keeps this path+action allowed across sessions.
    """
    if remember:
        grants = _load_grants()
        grants.setdefault(rel_path, {})[action] = True
        _save_grants(grants)
    else:
        _one_shot_grants.add((rel_path, action))
    log_event("permission_granted", {"path": rel_path, "action": action, "remember": remember})


def _consume_one_shot(rel_path: str, action: str) -> None:
    _one_shot_grants.discard((rel_path, action))


def revoke_all() -> None:
    """Wipes every remembered grant. One-time grants already consumed are unaffected."""
    _save_grants({})
    log_event("permissions_reset", {})


def guarded_list(rel_path: str = ".") -> list:
    if not is_granted(rel_path, "list"):
        raise PermissionDenied(f"listing '{rel_path}' was not granted")
    path = safe_path(rel_path)
    if not path.is_dir():
        raise NotADirectoryError(rel_path)
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
    log_event("file_list", {"path": rel_path})
    _consume_one_shot(rel_path, "list")
    return entries


def guarded_read(rel_path: str) -> str:
    if not is_granted(rel_path, "read"):
        raise PermissionDenied(f"read access to '{rel_path}' was not granted")
    path = safe_path(rel_path)
    if not path.is_file():
        raise FileNotFoundError(rel_path)
    content = path.read_text(errors="replace")
    log_event("file_read", {"path": rel_path})
    _consume_one_shot(rel_path, "read")
    return content


def guarded_write(rel_path: str, content: str) -> None:
    if not is_granted(rel_path, "write"):
        raise PermissionDenied(f"write access to '{rel_path}' was not granted")
    path = safe_path(rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    log_event("file_write", {"path": rel_path, "bytes": len(content)})
    _consume_one_shot(rel_path, "write")


def guarded_delete(rel_path: str) -> None:
    if not is_granted(rel_path, "delete"):
        raise PermissionDenied(f"delete access to '{rel_path}' was not granted")
    path = safe_path(rel_path)
    if not path.exists():
        raise FileNotFoundError(rel_path)
    if path.is_dir():
        raise IsADirectoryError(rel_path)  # only single files — no recursive folder deletes
    path.unlink()
    log_event("file_delete", {"path": rel_path})
    _consume_one_shot(rel_path, "delete")


# ---------------------------------------------------------------------------
# Audit log — plain JSON lines, human-readable, append-only
# ---------------------------------------------------------------------------
def log_event(kind: str, data: dict) -> None:
    entry = {"ts": round(time.time(), 3), "kind": kind, **data}
    with AUDIT_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
