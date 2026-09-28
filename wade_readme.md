# Wade — your local AI agent

One folder, nothing sent anywhere:

| File | What it does |
|---|---|
| `wade_server.py` | The backend. Talks to your local model, serves the page, runs tool calls, enforces every security rule. |
| `wade_security.py` | Auth token, rate limiting, and the file-permission gate — kept separate so it's easy to audit on its own. |
| `wade_index.html` | The interface. Signs itself in automatically, no copy-pasting a token. |
| `wade_start.sh` | Click-to-use launcher for Linux and Termux (Android) — run it from a terminal. |
| `wade_start.desktop` | Double-click launcher for Linux desktops — the same convenience as the Windows `.bat`. |
| `wade_widget.sh` | Tap-to-launch home-screen shortcut for Android, via the Termux:Widget app. |
| `wade_start.bat` | Click-to-use launcher for Windows — double-click it. |

## First-time setup

1. Put all the files in the same folder.
2. Get your model backend running — this differs by platform:
   - **Windows / Linux desktop — Ollama** (e.g. `ollama run llama3.2:3b`): that's all you need; Ollama already runs its own server in the background. This is the default Wade is configured for. On Linux, install it with `curl -fsSL https://ollama.com/install.sh | sh` if you don't have it yet.
   - **Android (Termux) — llama.cpp, not Ollama**: Ollama's install script targets standard Linux (glibc) and generally doesn't run properly inside Termux's Android environment. llama.cpp builds and runs natively in Termux instead, so that's what I'd point your phone at:
     1. Install **Termux from F-Droid** (not the Play Store version — it's outdated and no longer maintained).
     2. In Termux: `pkg update && pkg upgrade`
     3. `pkg install python clang cmake git`
     4. Build llama.cpp:
        ```bash
        git clone https://github.com/ggerganov/llama.cpp
        cd llama.cpp
        cmake -B build
        cmake --build build --config Release -j
        ```
        This produces `llama-server` under `build/bin/`.
     5. Get a small `.gguf` model onto the phone — a quantized ~0.5B model (e.g. Qwen2.5-0.5B-Instruct, Q4_K_M) is the safest fit for typical phone RAM; `llama3.2:3b` in GGUF form also works via llama.cpp on a higher-RAM phone (6GB+) if you'd rather match your desktop's model. Download it from Hugging Face into somewhere like `~/models/`.
   - **If you'd rather use raw llama.cpp on Windows/Linux too** instead of Ollama, that's supported the same way — get a `.gguf` model and a `llama-server` build for your OS.
3. Open the launcher for your OS and check the settings near the top match what you're running:

   **Windows** (`wade_start.bat`, right-click → Edit):
   ```bat
   set "WADE_BACKEND=ollama"
   set "WADE_MODEL_NAME=llama3.2:3b"
   set "WADE_PORT=7860"
   ```

   **Linux desktop** (`wade_start.sh`):
   ```bash
   export WADE_BACKEND="ollama"
   export WADE_MODEL_NAME="llama3.2:3b"
   export WADE_PORT="7860"
   ```

   **Android / Termux** (`wade_start.sh`) — switch to llama.cpp mode:
   ```bash
   export WADE_BACKEND="llamacpp"
   export WADE_MODEL_PATH="$HOME/models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
   export WADE_LLAMA_BIN="$HOME/llama.cpp/build/bin/llama-server"
   export WADE_PORT="7860"
   ```
   (Comment out or delete the `WADE_BACKEND`/`WADE_MODEL_NAME` Ollama lines already in the script so they don't override these.)
4. **Windows**: nothing else needed. **Linux / Termux**: make the launcher runnable once with `chmod +x wade_start.sh`.
5. **Linux desktop only, for the double-click launcher**: open `wade_start.desktop` in a text editor and change the `Exec=` line to the real, full path of `wade_start.sh` on your machine, e.g.:
   ```
   Exec=/home/yourname/wade/wade_start.sh
   ```
   Then `chmod +x wade_start.desktop`. The first time you double-click it, your file manager will likely ask you to confirm trust (GNOME Files: right-click → Properties → Permissions → "Allow executing file as program", or just choose "Allow Launching" the first time you open it) — that's normal one-time behavior for any `.desktop` file, not specific to Wade. After that it opens with one double-click, same as the Windows version. You can also copy it into `~/.local/share/applications/` to get a "Wade" entry in your applications menu.
6. **Android only, for a tap-to-launch home-screen icon**: install the **Termux:Widget** app (same source as Termux — F-Droid), then:
   ```bash
   mkdir -p ~/.shortcuts
   cp wade_widget.sh ~/.shortcuts/wade.sh
   chmod +x ~/.shortcuts/wade.sh
   ```
   Edit `WADE_DIR` near the top of `~/.shortcuts/wade.sh` to wherever you put Wade's files. Then long-press your home screen → Widgets → Termux:Widget → place it → tap the "wade" icon it shows. If you have Termux's `termux-api` add-on package installed, this also grabs a wake lock while Wade runs, so Android is less likely to kill it in the background.

## Using it

**Windows** — double-click `wade_start.bat`. A second window titled "Wade server" opens showing the live log (leave it open, close it to stop Wade), dependencies install automatically, and your browser opens to a page that's already signed in.

**Linux desktop** — double-click `wade_start.desktop` (after the one-time setup above), or run `./wade_start.sh` from a terminal — both do the same thing. A terminal window opens showing the live log; close it to stop Wade. If you have `notify-send` installed, you'll also get a desktop notification once Wade's ready.

**Android (Termux)** — run `./wade_start.sh` from a Termux session, after the llama.cpp setup above. Same behavior, minus the desktop notification. Keep the Termux app running in the background (or use the `wade_widget.sh` shortcut, which takes a wake lock if `termux-api` is installed) so Android doesn't kill it mid-chat.

All: installs Python dependencies, checks the model backend, starts the server, opens the browser to a page that's already signed in.

If you're using the Ollama backend and it isn't running yet, Wade tries to start it for you (`ollama serve`); if the model itself hasn't been pulled, pull it first with `ollama pull llama3.2:3b`. If you're using the llama.cpp backend (the Android/Termux default here), Wade tries to launch `llama-server` itself using `WADE_MODEL_PATH`/`WADE_LLAMA_BIN`.

To reach Wade from another device on the same Wi-Fi (phone ↔ laptop), open `http://<the-other-device's-LAN-IP>:7860` in the browser instead of `127.0.0.1` — this never touches the internet either way.

## Talking to Wade

- Type in the box, or tap one of the quick chips under the chat (Summarize a file, Debug some code, Browse workspace, தமிழில் பேசு) — those are one-click starting points so you don't have to type from a blank page every time.
- The **EN / தமிழ் / Auto** switch at the top controls what language Wade replies in. Auto matches whatever language you just typed in, and lets you mix Tamil and English (Tanglish) freely.
- Honest caveat: Llama 3.2 3B's officially supported languages don't include Tamil (English, German, French, Italian, Portuguese, Hindi, Spanish, and Thai are the ones Meta lists). It will often still attempt Tamil from what it picked up in training, but expect it to be noticeably less reliable than its English — if a Tamil reply looks off or garbled, asking it to explain in English usually gets you a clearer answer. If you're running a different model on Android (like Qwen2.5), its Tamil quality will differ — worth just testing it directly rather than assuming either way.

## Wade can now actually act, not just chat

Wade has four tools it can decide to use on its own: **list**, **read**, **write**, and **delete** files in your workspace. You can ask it things like *"what's in my notes folder?"* or *"create a to-do list from what I just told you"* and it will reach for the right tool itself — you don't have to open the Workspace drawer and fetch things manually anymore.

The permission model doesn't change because the AI is the one asking: **every single tool call still needs your Allow**, exactly like the manual Workspace browser. When Wade wants to touch a file, a dialog pops up naming exactly what it wants to do before anything happens — deny it and nothing happens, and Wade is told so and will explain that to you. A dashed line in the chat (e.g. *"🔧 Wade read notes/sample.txt"*) records every action that actually ran, so there's always a visible trail. Tick "Remember this choice" the same as before if you don't want to be asked again for that specific file and action.

One deliberate trade-off: since Wade may need to make several tool calls before it can answer, replies now arrive as a complete message (with a quick word-by-word reveal for polish) rather than streaming live token by token the way the first version did. That's a reliability choice — this is a small model asked to plan multi-step actions correctly, and getting it right on every attempt matters more than the typing animation.

I scoped Wade's tools deliberately to the same guarded workspace folder rather than giving it the ability to run shell commands or touch the rest of your system — that stays true to the "more secure" requirement this was built around. If you want Wade to be able to do something specific beyond file read/write/delete (e.g. run a particular script), that would need to be added as its own narrowly-scoped, permission-gated tool rather than opening general system access.

## Files and permissions

Wade can only ever see one folder: `~/wade_workspace` (that's `%USERPROFILE%\wade_workspace` on Windows — e.g. `C:\Users\YourName\wade_workspace`). Nothing outside it is reachable, even if you ask.

Every single read, write, delete, or folder listing pops up an **Allow / Deny** dialog first — whether it's you browsing or Wade asking mid-conversation — and by default that permission is used once and then asked again next time. If you tick **"Remember this choice"** in the dialog, that specific file and action stay allowed across sessions until you clear it. To reset everything back to asking every time:

**Windows (PowerShell):**
```powershell
$token = Get-Content "$env:USERPROFILE\.wade\token.txt"
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:7860/api/files/revoke-all" -Headers @{ "X-Wade-Token" = $token }
```
**Linux / Termux:**
```bash
curl -s -X POST http://127.0.0.1:7860/api/files/revoke-all -H "X-Wade-Token: $(cat ~/.wade/token.txt)"
```

## Security, at a glance

- **Token**: generated once, stored at `~/.wade/token.txt` (`%USERPROFILE%\.wade\token.txt` on Windows), and injected into the page automatically by the server — it never appears in a URL or a copy-paste step.
- **Rate limiting**: chat and file requests are capped per minute so nothing can be hammered accidentally or otherwise.
- **Path safety**: every file path is resolved and checked against `~/wade_workspace` before anything touches disk — there's no way to walk out of that folder.
- **Audit log**: every grant, denial, read, write, delete, and rejected request is appended to `~/.wade/audit.log` as plain JSON lines, so you can see exactly what Wade did and when — including which ones Wade itself requested versus ones you triggered by browsing.
- To invalidate the current token and force a fresh sign-in, delete `~/.wade/token.txt` and restart `wade_server.py`.

## If something doesn't work

- **"offline" / red status light**: the model backend isn't running. Check the terminal / "Wade server" window for errors — most commonly Ollama isn't installed, isn't running, or `WADE_MODEL_NAME` doesn't match a model you've pulled (`ollama list` shows what you have).
- **Page loads but chat fails immediately**: the model started but crashed or ran out of memory. Try a smaller quantization or close other apps first.
- **"too many requests"**: the rate limiter kicked in — wait a few seconds and try again.
- **A file won't open**: click Allow in the permission dialog — Wade never reads anything without it, by design.
- **Wade never seems to use a file even when it should**: tool-calling depends on your backend supporting it. On Ollama, make sure you're on a reasonably recent version (`ollama --version`). On llama.cpp (the Android/Termux path), make sure your build is recent and you're using a model whose chat template supports tool calls — Qwen2.5-Instruct models are a reliable choice; some older or non-instruct models don't support this at all.
- **Windows: "'python' is not recognized"**: reinstall Python from python.org and tick "Add python.exe to PATH" — then close and reopen the terminal or double-click the launcher again.
- **Windows: a firewall prompt appears the first time you run it**: click "Allow access" for private networks — that's Windows asking permission for the local server, not Wade reaching the internet.
- **Linux: double-clicking `wade_start.desktop` opens it as text, or does nothing**: it needs to be marked as a trusted, executable launcher first — see step 5 under First-time setup above (`chmod +x` plus your file manager's one-time "Allow Launching" confirmation).
- **Android: `ollama` commands don't work in Termux**: expected — Ollama isn't a good fit for Termux's environment. Use the llama.cpp setup described above instead (`WADE_BACKEND=llamacpp`).
- **Android: `cmake`/`git` not found, or the build fails**: run `pkg update && pkg upgrade` first, then re-install `pkg install python clang cmake git` — a stale Termux package index is the most common cause.
- **Android: Wade gets killed a few minutes after you switch apps**: Android is stopping the Termux process to save battery. Open Termux's own Android app settings and disable battery optimization for it, and/or install the `termux-api` package so `wade_widget.sh` can hold a wake lock.
- **Android: tapping the Termux:Widget icon does nothing or errors**: confirm the script is a real file (not a symlink) at `~/.shortcuts/wade.sh`, is executable (`chmod +x`), and that `WADE_DIR` inside it points at the real folder with Wade's files.
- **Android: replies are very slow or the phone gets hot**: expected for a 3B model on a phone — try the smaller Qwen2.5-0.5B model instead, and close other apps to free RAM.
