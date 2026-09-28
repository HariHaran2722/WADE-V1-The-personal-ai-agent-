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