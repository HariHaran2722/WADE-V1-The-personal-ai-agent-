# Wade — Linux setup

Your local AI agent. One folder, nothing sent anywhere.

| File | What it does |
|---|---|
| `wade_server.py` | The backend. Talks to your local model, serves the page, runs tool calls, enforces every security rule. |
| `wade_security.py` | Auth token, rate limiting, and the file-permission gate — kept separate so it's easy to audit on its own. |
| `wade_index.html` | The interface. Signs itself in automatically, no copy-pasting a token. |
| `wade_start.sh` | Click-to-use launcher — run it from a terminal. |
| `wade_start.desktop` | Optional double-click launcher for your desktop/app menu. |

## First-time setup

1. Put all the files in the same folder.
2. Install **Ollama** if you don't have it: `curl -fsSL https://ollama.com/install.sh | sh`, then get a model: `ollama run llama3.2:3b`. Ollama runs its own server in the background once installed — that's all Wade needs.
3. Open `wade_start.sh` and check the settings near the top match what you're running:
   ```bash
   export WADE_BACKEND="ollama"
   export WADE_MODEL_NAME="llama3.2:3b"
   export WADE_PORT="7860"
   ```
   (If you'd rather use raw llama.cpp instead of Ollama, get a `.gguf` model and a `llama-server` build, set `WADE_BACKEND=llamacpp`, and uncomment/set the `WADE_MODEL_PATH` line below it.)
4. Make the launcher runnable once: `chmod +x wade_start.sh`
5. **Optional, for a double-click launcher**: open `wade_start.desktop` in a text editor and change the `Exec=` line to the real, full path of `wade_start.sh` on your machine, e.g.:
   ```
   Exec=/home/yourname/wade/wade_start.sh
   ```
   Then `chmod +x wade_start.desktop`. The first time you double-click it, your file manager will likely ask you to confirm trust (GNOME Files: right-click → Properties → Permissions → "Allow executing file as program", or just choose "Allow Launching") — that's normal one-time behavior for any `.desktop` file. You can also copy it into `~/.local/share/applications/` to get a "Wade" entry in your applications menu.

## Using it

Double-click `wade_start.desktop` (after the one-time setup above), or run `./wade_start.sh` from a terminal — both do the same thing: install Python dependencies, check the model backend, start the server, and open your browser to a page that's already signed in. A terminal window opens showing the live log; close it to stop Wade. If you have `notify-send` installed, you'll also get a desktop notification once Wade's ready.

If Ollama isn't running yet, Wade tries to start it for you; if the model itself hasn't been pulled, pull it first with `ollama pull llama3.2:3b`.

To reach Wade from your phone on the same Wi-Fi, open `http://<this-machine's-LAN-IP>:7860` in the phone's browser instead of `127.0.0.1` — this never touches the internet either way.

## Talking to Wade

- Type in the box, or tap one of the quick chips under the chat (Summarize a file, Debug some code, Browse workspace, தமிழில் பேசு) — those are one-click starting points so you don't have to type from a blank page every time.
- The **EN / தமிழ் / Auto** switch at the top controls what language Wade replies in. Auto matches whatever language you just typed in, and lets you mix Tamil and English (Tanglish) freely.
- Honest caveat: Llama 3.2 3B's officially supported languages don't include Tamil (English, German, French, Italian, Portuguese, Hindi, Spanish, and Thai are the ones Meta lists). It will often still attempt Tamil from what it picked up in training, but expect it to be noticeably less reliable than its English — if a Tamil reply looks off or garbled, asking it to explain in English usually gets you a clearer answer.

## Wade can act, not just chat

Wade has four tools it can decide to use on its own: **list**, **read**, **write**, and **delete** files in your workspace. Ask it things like *"what's in my notes folder?"* and it reaches for the right tool itself.

The permission model doesn't change because the AI is the one asking: **every single tool call still needs your Allow**. A dialog names exactly what Wade wants to do before anything happens — deny it and nothing happens. A dashed line in the chat (e.g. *"🔧 Wade read notes/sample.txt"*) records every action that actually ran. Tick "Remember this choice" if you don't want to be asked again for that specific file and action.

One trade-off: since Wade may make several tool calls before answering, replies arrive as a complete message (with a quick word-by-word reveal for polish) rather than streaming live token by token.

Wade's tools are scoped to its own workspace folder only — no shell access, no system-wide control.

## Files and permissions

Wade can only ever see one folder: `~/wade_workspace`. Nothing outside it is reachable, even if you ask.

Every single read, write, delete, or folder listing pops up an **Allow / Deny** dialog first — whether it's you browsing or Wade asking mid-conversation — and by default that permission is used once and then asked again next time. Tick **"Remember this choice"** to keep a specific file and action allowed across sessions. To reset everything back to asking every time:

```bash
curl -s -X POST http://127.0.0.1:7860/api/files/revoke-all -H "X-Wade-Token: $(cat ~/.wade/token.txt)"
```

## Security, at a glance

- **Token**: generated once, stored at `~/.wade/token.txt` (owner-read-only), and injected into the page automatically by the server — it never appears in a URL or a copy-paste step.
- **Rate limiting**: chat and file requests are capped per minute.
- **Path safety**: every file path is resolved and checked against `~/wade_workspace` before anything touches disk — no way to walk out of it.
- **Audit log**: every grant, denial, read, write, delete, and rejected request is appended to `~/.wade/audit.log` as plain JSON lines.
- To force a fresh sign-in, delete `~/.wade/token.txt` and restart `wade_server.py`.

## If something doesn't work

- **"offline" / red status light**: the model backend isn't running. Check the terminal for errors — most commonly Ollama isn't installed, isn't running, or `WADE_MODEL_NAME` doesn't match a model you've pulled (`ollama list` shows what you have).
- **Page loads but chat fails immediately**: the model started but crashed or ran out of memory. Try a smaller quantization or close other apps first.
- **"too many requests"**: the rate limiter kicked in — wait a few seconds and try again.
- **A file won't open**: click Allow in the permission dialog.
- **Wade never seems to use a file even when it should**: tool-calling needs a reasonably recent Ollama version — check with `ollama --version` and update if it's old.
- **Double-clicking `wade_start.desktop` opens it as text, or does nothing**: it needs to be marked as a trusted, executable launcher first — see step 5 under First-time setup (`chmod +x` plus your file manager's one-time "Allow Launching" confirmation).
