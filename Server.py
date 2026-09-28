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