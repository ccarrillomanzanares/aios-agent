# Changelog

## v0.23.0 - 2026-09-12 19:12

### features

- **The AIOS LLM is now Qwen3.6-35B-A3B** (MoE, ~3B active of 35B, multimodal) instead of the fine-tuned Nemotron-3.5-Lightning. It does **text AND vision in one model**, so the separate vision container is gone.
  - Chosen over the Nemotron for three measured reasons: **Apache 2.0 license** (the Nemotron was OpenMDW-1.1, with a patent clause — relevant for a globally distributed ISO), **identical behaviour in thinking ON and OFF** (94.3% in both modes, vs 97.1%/91.4% for the Nemotron), and **better tool-call discipline** (`CONFIRM` 3/4 vs 2/4, `TOOL` 17/17 vs 16/17 in the OFF mode).
  - The Nemotron was faster (~26 tok/s vs ~9 tok/s on the CPU-only VPS) and scored slightly higher on thinking ON. Both trade-offs were accepted by Carlos after using it: *"lo noto muchísimo mejor que cualquier otro agente/llm que hemos probado"*.
  - Weights: `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` (21.1 GB) + `mmproj-qwen3.6-F16.gguf` (858 MB).
- **Vision now goes through the same model.** `describe_screen()` points at the chat endpoint, so there is one model to run and one route to maintain instead of two.
  - Verified with a purpose-made image (text `RACK 7 TEMP 63C`) — the model read it back exactly.
  - Verified on a real desktop: it reported the **window title** (`bios@aios:~`), the user, the hostname and what the terminal was doing. The previous 4B model could not do this.
  - The `/vision/*` route and the `llama-vision` container (Gemma-3-4B + mmproj) were removed; the `vision.endpoint` default now points at the chat endpoint.
- **`/v1` is kept as a legacy alias** and now serves the same model as `/ollama`, so existing configurations and any client pointed at `/v1` keep working unchanged.

### fixes

- **`describe_screen()` returned an EMPTY description.** It was the only LLM call in the agent that did **not** send `enable_thinking`; the model reasoned by default, spent all 400 `max_tokens` on `reasoning_content` and returned an empty `content`. Fixed by sending `enable_thinking: false`, like every other call in the agent. This bug existed before this release — the previous model happened to work anyway.
- **`setup.py` would configure a broken installation.** The model list for the VPS provider still offered `nemotron-3.5-lightning` (removed) and `qwen3.5:9b` (no longer served), and the vision option wrote the now-removed `/vision` endpoint. Both corrected to the live model and endpoint.

### infra

- The `llama-hardened` stack is now **two containers** (`proxy` + `qwen`) instead of four. Removed: the `llama` (Nemotron) and `vision` (Gemma) services, their entrypoints, their Dockerfile `COPY` lines, the `/vision` Caddy block, the `depends_on` that referenced the removed service, the two Nemotron GGUFs (48 GB), the two Gemma GGUFs (3.3 GB), a stray second Gemma server that had been running unattended on port 8095 for 3 days, and the dead `k2-test` tree.
- Free space on the VPS went from **60 GB to 136 GB**; RAM in use dropped from 30.5 GB to ~15 GB.
- Backups of every file touched are in `~/llama-hardened/.bak-qwen36/`.

## v0.22.0 - 2026-09-11 23:55

### fixes

- **The AIOS LLM (Nemotron-3.5-Lightning, fine-tuned) now works with thinking ON *and* OFF, both with tool calling.** The previous fine-tune returned an **empty response** (1 token, `finish=stop`) whenever `enable_thinking=false`: the agent went mute on any request that needed a tool call ("hello" answered, "check the running containers" did not).
  - Root cause: at training time the chat template was rendered **without** `enable_thinking`, so it emitted a **closed, empty reasoning block** (` thinking`) in front of the tool call. The model learned that transition and was out of distribution when a real reasoning block opened at inference.
  - Fix in the re-training: `mask_generation_prompt: true` + `mask_reasoning_content: true` (the template's own tokens are no longer supervised), tool-call `arguments` kept as a **mapping** (the Nemotron template iterates them with `|items`), and `model.output_hidden_states: true`.
  - Verified against the public endpoint in **both** modes: `run_command {"command":"sven install vim"}` — with `enable_thinking: true` and `false`.
- **Model, dataset, recipes and scripts are now versioned** in the `aios-model` repo: behaviour dataset (249 pairs, 154 with real `tool_calls`), NeMo AutoModel recipes, the manual tensor-merge script and the training/deploy scripts.
- The `enable_thinking` cloud patch in `agent.py` is no longer required: the model handles both modes, so `/think on` and `/think off` both work.

## v0.21.0 - 2026-09-11 22:30

### features

- **BitTorrent client with media playback** (new module `torrent.py` + 5 agent tools). The user asks in plain language ("I want to watch Metropolis by Fritz Lang") and the agent searches, downloads and plays — no GUI needed.
  - `torrent_search(query)` — searches **apibay.org** (The Pirate Bay API) and **torrents-csv.com**, merges and ranks by seeders, caches the numbered list so `torrent_download("<number>")` just works. Verified: "Metropolis 1927 Fritz Lang" → restored 1080p release, 115 seeders.
  - `torrent_download` / `torrent_status` / `torrent_control` (start|stop|verify|remove|remove-data) — driven through the **transmission-daemon** RPC on 127.0.0.1:9091.
  - `torrent_play([id])` — plays with **mpv** fullscreen (ffmpeg does the decoding); with no id it plays the newest media file downloaded.
  - Verified end-to-end on the build tree: 263 MB torrent downloaded to 100% in 70 s (9.76 MB/s, 50 peers), then stop + remove-data clean.
- **aria2c** for plain HTTP/FTP/FTP-magnet documents (PDFs, archives) — `torrent.fetch()`.
- New packages installed with sven (official repos only): `transmission-cli` 4.1.3-2, `aria2` 1.37.0-3, `mpv` 0.41.0-6 (+ `ffmpeg`/`libbluray` refreshed to the same upstream so `libbluray.so.4` and `so.3` coexist).
- Config in `/etc/aios-torrent.conf` (system defaults, shipped in aios-lfs) with a per-user override in `~/.aios/torrent.conf`; downloads default to `~/Downloads`.
- `aios-update` deploys `torrent.py` and the new system configs (previously the manifest would have silently skipped them).

### fixes

- **transmission-daemon runs as the desktop user**: the Arch unit uses `User=transmission` (uid 169) and `/var/lib/transmission`, so downloads would not be readable/deletable by the user who watches them. New drop-in `transmission-daemon.service.d/user.conf` (aios-lfs) sets `User=aios`, `HOME`/XDG under `/home/aios` and `--download-dir /home/aios/Downloads`. No `Group=` line: AIOS' user aios has primary group `wheel`, and a wrong `Group=` fails the unit with 216/GROUP.
- The daemon is **not enabled at boot** — `torrent.py` starts it on demand (systemctl, NOPASSWD in the AIOS live/installed model, with a direct-launch fallback), so an unused system keeps no extra service or open peer port.
- Magnet building: Transmission 4.1.3 rejects a percent-encoded `xt=urn%3Abtih%3A<hash>` with "unrecognized info" — the xt value is now emitted verbatim (raw colons), only `dn`/`tr` are encoded.

## v0.20.0 - 2026-09-09 12:45

### features

- **AI vision (optional)**: new `describe_screen()` tool — captures the screen and describes it with **Gemma-3-4B** (multimodal VLM) on the VPS. Recognizes apps, logos and UI text (verified: identified the Grafana editor, "Prometheus default", "Kick start your query"...).
- **llama-hardened stack extended**: third container `llama-vision` (Gemma-3-4B Q4_K_M + mmproj) on `/vision/*` with the same X-API-Key. Analysis takes ~43s (12.6s prompt + 30.8s gen).
- **Optional for privacy**: setup asks *"Enable vision?"* (only for the LLM VPS provider). If declined, the agent keeps using browser/OCR. Config stores `vision.enabled` + endpoint + key.
- **Model ladder tested**: SmolVLM-256M (175MB) ❌, SmolVLM-500M (437MB) ❌, SmolVLM2-2.2B (1.9GB) ⚠️ imprecise, **Gemma-3-4B (2.5GB) ✅** — the smallest that works.

### fixes

- **Anti-hallucination compression**: the LLM summary is verified against real keywords from the history; if it does not mention them (K2 invented a fake Node.js/MongoDB conversation), it is rejected and an honest summary is used.
- **K2 tamed**: `MAX_TOKENS` 2048 + `reasoning_effort: low` + 240s watchdog + no retry — a turn no longer burns 40 min thinking.
- **API-FIRST prompt**: `fetch()` from `browser_eval` for authenticated web apps (Grafana, Prometheus, Jenkins, GitLab...).
- **browser_eval prompt**: returns value (not console.log) + small steps in UI.
- **OCR**: uses only installed languages (eng) instead of eng+spa which failed.
- **Software inventory**: auto-record installs/removals + `get_installed_info` tool + markdown fact sheets.
- **Anti-loop order fix**: the loop guard now runs BEFORE the "command previously failed" guard (which used `break` and skipped the counter — K2 looped ~18x on the same failing command). `continue` (not `break`) + whitespace-stripped args.
- **Cleanup**: removed dead tools from the registry and code (`mcp_call`, `run_playbook`, `process_send`, module `playbook.py`); deleted the discarded vision-ladder GGUFs on the VPS (SmolVLM 256M/500M/2.2B) — only K2 + Gemma-3-4B remain; vision policy added to the prompt (describe_screen → browser_eval → ocr → screenshot).

## v0.19.0 - 2026-09-08 22:40

### features

- **"LLM VPS (llama-hardened)" provider** in setup: selectable alongside cloud providers, with two models:
  - `k2-horizon:7b` → `webuillama.ccmai.org/v1/chat/completions` (K2-Horizon-7B Q4_K_M, llama-server fork MBZUAI-IFM)
  - `qwen3.5:9b` → `webuillama.ccmai.org/ollama/v1/chat/completions` (Qwen3.5-9B, same stack, separate route)
  - Same `X-API-Key` for both; the menu propagates the URL per model (3rd tuple element).

### breaking change

- **Ollama Hardened → llama-hardened**: the VPS stack changes engine. `ollama-core` (Ollama 0.32.15) cannot serve K2 (MoVA architecture not yet supported in its llama.cpp), so the stack moves to **llama-server from the MBZUAI-IFM fork** behind Caddy X-API-Key. `/v1` serves K2 and `/ollama/*` serves Qwen3.5. Ollama stays stopped as reserve (models intact in its volume).

## v0.18.6 - 2026-09-08 17:05

### features

- **Barge-in (interrupt the agent)**: during the agent's turn (while it writes or runs tools), **Tab** pauses and opens a mini-input to add more information by text; **Ctrl+R** captures info by voice (microphone + STT). The turn is cut gently and the agent relaunches with the info as a new query, keeping context. No Ctrl+C. Documented in `shortcuts.txt` (F1).
- **browser_elements**: new tool that inventories the page's interactive elements (buttons, links, inputs) as readable refs (`btn-create-dashboard`, `inp-search`) with visible text and CSS selector — the agent SEES the page before clicking (like Hermes `drive_preview action="elements"`).
- **browser_click/browser_type with text fallback**: if the selector doesn't exist, it searches by visible text (`innerText`/`aria-label`/`value`/`placeholder`, case-insensitive) — click by what you SEE ("Create your first dashboard") without guessing selectors.
- **Browser prompt updated**: the agent must call `browser_elements()` BEFORE clicking/typing (workflow navigate → elements → click/type).

### fixes

- **token estimator len//2** (overestimates for all European languages, measured 2.8-4.4 chars/token real vs 2 estimated): compresses earlier, never reaches Cloudflare's 100s limit.
- **compression loop (max 3 passes)**: if after compressing the history is still above the threshold, compress again — the final prompt always fits.
- **2000 char cap on the text to summarize**: the compression call is light (~15-20s) even with a huge history.

## v0.18.5 - 2026-09-07 20:21

### features

- **Chromium + CDP (browser_*)**: new tools `browser_navigate`, `browser_eval`, `browser_click`, `browser_type` — real browser control via DevTools Protocol (real DOM, clicks by selector, forms by field). No more blind OCR. Chromium 152 installed from sven.
- **Browser prompt**: the agent uses `browser_*` to browse (never `process_send` — browsers ignore stdin); documented workflow (navigate → eval → click → type).
- **Dynamic installer banner**: `aios-install` reads the version from the CHANGELOG (shows `AIOS LFS INSTALLER v0.18.5` instead of the hardcoded `1.1.3`).

### fixes

- **silent voice (root cause)**: the tic aplay holds the PCM device; TTS launched another aplay → `Device or resource busy` silenced. Fix: close/reopen the tic aplay INSIDE the `_speak_sync` thread (voice.py) — `speak()` spawns a thread and returns, so closing in chat.py reopened before TTS opened the device.
- **browser did not navigate**: `_ensure_browser()` used `_urlopen` without importing it (silent NameError) in the check and in the wait loop → 10s timeout. Fix: `urllib.request as _url` in both + 30s wait (Chromium takes a while to start on the laptop).
- **aios-diag not executable**: mode 100755 in git (the `/usr/local/bin/aios-diag` wrapper had no `x`).

## v0.18.4 - 2026-09-07 15:58

### fixes

- **laptop boot (boot race)**: getty@tty1 launched X before udev applied permissions to `/dev/dri/card0` -> `open /dev/dri/card0: Permission denied` -> `no screens found` -> getty loop -> `start-limit-hit` -> blinking cursor with no session. `aios-session` now waits up to 30s for `/dev/dri/card0` to be readable/writable before `startx`.
- **laptop audio (same race)**: `audio-detect.py` ran 9s into boot, when only the HDMI card was visible -> wrote `plughw:0,0` (HDMI) instead of the analog one. Now if the only detected card is HDMI, it waits and retries (up to 15s) until the analog card appears.
- **deploy**: `aios-deploy-and-build.sh` now copies `scripts/aios-session` and `scripts/audio-detect.py` to the tree (they never reached the ISO before).

## v0.18.3 - 2026-09-07 08:06

### fixes

- **HTTP timeout 120s -> 300s**: long CPU generations (e.g. stories, long answers) exceeded the 120s limit and the agent cut with `Read timed out`. The POST took 2m5s on ollama-core (prompt-eval + generation at 4-8 tok/s) and the client died first.
- **compression summary as `user` (not `system`)**: the no-thinking model `frob/qwen3.5-instruct:9b` requires `system` at the start of the history; a summary inserted as `system` in the middle caused 500 `Jinja Exception: System message must be at the beginning`.
- **cloud compression threshold 20% -> 10%**: keeps prompt-eval (~25 tok/s on CPU) under the timeout with large contexts.
- **tool output cap**: ANSI strip + truncation to 1200/1000 chars (was 5000/2000) — command outputs no longer bloat the context and slow the reasoning model.
- **MAX_TURNS 10 -> 25** + when exhausted the agent asks `(continue) I haven't finished yet... Do you want me to continue?` instead of `(no response)`.
- **procedural memory filter**: no longer caches greetings/trivial queries (hola, gracias, ok...), short answers (<80 chars) or `(continue)` status messages.
- **OCR eng+spa**: tesseract with Spanish for Spanish pages.
- **bracketed paste in `_read_line()`** (setup.py): copy/paste works in the API key prompt.
- **dynamic version banner**: `AIOS/v0.18.3` is read from the CHANGELOG (auto-updates with each release) instead of the hardcoded `AIOS/1.4`.
- **Wargames teletype tick**: 4kHz transient + 250Hz body, half volume, with `--period-size=128` (tick per character, no bursts); the user-typing tick is removed (only the agent's typewriter sounds).

### note

- The WordPress example in the system prompt was reverted (back to the original `do NOT explain - EXECUTE`); the OCR preprocessing (2x+psm 11) was reverted due to timeout — OCR vision stays as-is (limitation of the 9B model without real vision).

## v0.18.2 - 2026-09-04 23:21

### fixes

- **docker group not created on install (systemd ALPM hooks missing)**: `sven install docker` installed the binaries but `docker.socket` failed with `status=216/GROUP` "Unknown group 'docker'". The docker package ships `usr/lib/sysusers.d/docker.conf` (`g docker - -`), processed by `systemd-sysusers` via the `20-systemd-sysusers.hook` — but those hooks ship with Arch's `systemd` package, absent here because AIOS builds systemd from LFS base. Added the systemd hooks (`20-systemd-sysusers`, `21-systemd-tmpfiles`, `25-systemd-hwdb`, `25-systemd-sysctl`, `30-systemd-daemon-reload-system` + `scripts/systemd-hook`) to the tree. Verified end-to-end: uninstall → delete group → reinstall → hook fires automatically and creates the group.
- **docker socket not connecting (LFS symlinks missing)**: `/var/run` and `/var/lock` were real empty directories (owner ccmai, dated Jun 21) instead of the LFS symlinks `/var/run → /run` and `/var/lock → /run/lock` (LFS book §7.5); `/etc/mtab → /proc/self/mounts` was missing entirely. `dockerd` listens on `/var/run/docker.sock` while `docker.socket` creates `/run/docker.sock`, so they never connected ("no such file or directory"). Root cause: the Jun 21 `mksquashfs` over an overlay mount omitted **absolute** symlinks pointing at chroot mount points (relative symlinks survived). Recreated the 3 symlinks in the tree and installed disks.
- **build hardening**: `aios-deploy-and-build.sh` now verifies/recreates the 3 LFS symlinks before every `mksquashfs`, so a rebuilt tree can't silently lose them again.

## v0.18.1 - 2026-09-04 17:58

### fixes

- **installer password bug (critical)**: `aios-install` used `getpass.getpass()` for the root/aios passwords, but the terminal is left in a dirty (raw) state by the earlier `_read_line()` menus — `getpass` then reads the password corruptly, so the passwords set during installation do not work at first login. Replaced with a self-contained `_read_password()` that masks input with `*` and controls the tty directly.
- **installer chroot ordering bug (critical)**: `cleanup_chroot()` (which unmounts `/proc`, `/sys`, `/dev`, `/run` from the target) ran **before** `set_passwords()`, `harden_login()`, `harden_ssh()` and `add_user_groups()`. Those functions `chroot` into the target and run `chpasswd` / `systemctl enable` — with `/proc` unmounted they fail silently, so `sshd` was never enabled and password/PAM setup could be incomplete. Reordered so `cleanup_chroot()` runs last, just before the final `umount`.
- **`aios-install` line endings**: forced LF in `.gitattributes` (it is a Linux script; CRLF broke the shebang and the Python string literals during editing).
- **installer password bug — real root cause (PAM)**: `/etc/pam.d/system-auth` was truncated to a single line (`auth required pam_unix.so`) with no `account`/`session`/`password` stacks. `chpasswd` invokes `password include system-auth`, which was empty → `pam_chauthtok() failed: Authentication token manipulation error` → new passwords were never written to `/etc/shadow` (factory `root:root`/`aios:aios` still worked). Restored the full BLFS `system-auth` (auth+account+session+password `pam_unix.so`). Verified in a real chroot: `chpasswd` now changes the hash and `unix_chkpwd` authenticates.
- **agent anti-loop removed**: the "3 identical tool calls" detector caused false positives on legitimate retries (e.g. `sven install` after a network timeout) and crashed with `NameError: _tool_history`. Replaced with a simpler guard that only refuses to re-run a `run_command` that already failed with the same command string.
- **sudo password asked inline**: removed the `/sudo <password>` round-trip. `run_command` now prompts for the sudo password (masked `*`) directly when a command needs it, runs the command in the same turn, and caches it for the session — no more "run /sudo" loop that broke the action chain.
- **timezone selector**: `setup.py` now sets the timezone alongside NTP (menu option "3) Set date & time" and the install flow). Universal hierarchical picker (continent → region → city) with free-text input and suggestions, reading tzdata directly (no hardcoded zone). `aios-install` persists `/etc/localtime` to the disk so the zone chosen in live mode carries over.

## v0.18 - 2026-08-31 19:48

### new features

- **local LLM — Qwen3.5-9B**: the bundled local model is now **Qwen3.5-9B** (Q4_K_M), replacing Qwen3-8B — better reasoning and tool calling. `llama-server` upgraded to **b10655** (CPU-dispatched: runs on any x86-64, from SSE4.2 to AVX-512).

### fixes

- **cloud empty responses**: the Ollama Hardened server now serves `qwen3.5:9b` with a **32K context window** (`OLLAMA_CONTEXT_LENGTH=32768`) instead of the 4K default — fixes empty responses where reasoning + tool-calling exhausted the context.
- **agent empty-response diagnostics**: on an empty response the agent now reports the cause (`finish_reason`, reasoning characters emitted) instead of the generic "(empty model response)".

## v0.17.2 - 2026-08-30 22:49

### fixes

- **audio**: `aplay` now uses a minimal period/buffer (`--period-size=512 --buffer-size=1024`) so the typewriter tic sounds per-character instead of accumulating into a continuous beep.
- **volume keys**: the i3 volume bindings now use `amixer set Master` (the same ALSA mixer `aplay`/`plughw` uses) instead of `pactl` (PipeWire), so the keys actually change the volume.
- **setup note**: keyboard shortcuts indicate that chat commands (`/sound`, `/voice`, `/theme`) work after setup (once the agent/LLM starts).
- **Ollama Hardened provider**: endpoint moved to `:443` (valid cert via Cloudflare) and TLS verification enabled by default (`VERIFY_TLS` no longer tied to `x-api-key`); model switched from Moonlight (no function calling) to `qwen3.5:9b`.
- **context/tokens**: cloud `max_tokens` now scales with the context (`_cloud_context // 4`) instead of a fixed 4096, and the Ollama Hardened `context_limit` raised 8K → 32K — fixes empty responses from reasoning models exhausting the token budget.
- **status bar**: `CTX` block now resolves the Ollama Hardened context limit (32K) instead of the 128K default.

## v0.17.1 - 2026-08-30 14:10

### fixes

- **audio**: `aios-audio.service` was never enabled (missing `multi-user.target.wants` symlink), so `audio-detect.py` didn't run at boot and `asound.conf` kept the hardcoded `plughw:1,0`. Now enabled — the analog card is auto-detected (e.g. `plughw:0,0` on HDA Intel PCH).
- **sven**: `run_command` passed both `stdin` and `input` to `subprocess.run`, so `sven update`/`upgrade`/`install` failed with "stdin and input arguments may not both be used". Fixed — `input` implies PIPE.
- **sudo**: the agent now detects NOPASSWD (`sudo -n true`). In live (NOPASSWD) `sudo` runs directly without a password; in the installed system (password) it asks for `/sudo <password>` (in-memory only, never persisted to disk).

## v0.17 - 2026-08-30 01:48

### new features

- **sudo with password**: `/sudo <password>` (cached in session) + `run_command` uses `sudo -S`; the agent accepts the password in local and cloud modes (no NOPASSWD needed).
- **audio-detect.py**: autodetects the analog sound card and writes `asound.conf` dynamically — audio works on any hardware.

### i18n

- All comments and user-facing strings translated to English (agent, installer, README, docs, scripts). Fixes ` thinking` tag corruption.

### quotes

- **5 Terminator quotes** (T1 + T2) and **2 Matrix quotes** (the full red pill / blue pill monologue + "Whoa. Déjà vu."). Quote lists unified (`setup.py` was missing Blade Runner) + shuffle-cycle picker to avoid repeats.

### fixes

- Don't auto-open Firefox for the API key (ask first).
- Login cursor: remove `vt.global_cursor_default=0` from the disk GRUB entry.
- Audio/voice/chat patches.
- Restore `scripts/aios-diag` exec bit.

### license

- MIT license added.

## v0.16 - 2026-08-29 09:06

### voice (TTS/STT) — independent `voice:` section from chat

- **Config**: `voice:` section in `config.yaml` (tts/stt/tts_lang), separate from `cloud:` (chat). Setup (live and `aios-install`) lets choose TTS (off/espeak/gemini/openai), STT (off/vosk/gemini/openai) and language; voice keys go to `~/.aios/.env` apart from chat (`GOOGLE_API_KEY`/`OPENAI_API_KEY` vs `DEEPSEEK_API_KEY`).
- **TTS** (`voice.py`): local espeak-ng (no key), Gemini `gemini-2.5-flash-tts` and OpenAI `gpt-4o-mini-tts` (cloud). Skips code blocks/tables so it doesn't spell them out, and speaks in a thread (does not block chat). `espeak-ng` installed via sven.
- **STT** (`voice.py`): local vosk, Gemini and OpenAI cloud (records with `arecord`).
- **Commands**: `/voice` (toggles voice, persists) and `/mic` (records + transcribes + sends as message).
- **Icon**: `VOX/MIC` block in the i3 bar (green=active, dimmed=off) reading `data/voice_state.json`.

### fixes

- **Beep/tic did not sound**: `aplay --buffer-size=512 --period-size=512` (buffer == period) failed silently on some codecs; removed (device defaults). `aios-diag` now collects audio state (`aplay -l`, `/proc/asound/cards`, `amixer`, snd/hda errors).
- **Loading bar in English**: the LLM progress bar text was in Spanish; switched to English (consistent with the rest of the printf).

## v0.15 - 2026-08-29 08:09

### fixes for LLM boot and screenshot (progress bar regression)

- **LLM loading stuck at 85%**: `_start_local_model` used `select` on raw fd + `readline` with Python buffer. When llama-server wrote `model loaded` and `listening` almost together, `readline` read both lines into buffer but returned only the first; `listening` stayed stuck in the buffer (select watches the fd, not the buffer) and the bar stayed at 85% forever **even though the server was already listening** (hence 0% CPU and "does not finish"). Fix: **reader thread + queue** (no select) that drains stdout and detects `listening` for real; 15 min timeout and dump of the last lines if it doesn't start.
- **Printscreen (`Print`)**: inline `scrot` in i3 with `%` (strftime) + `&&` + nested quotes broke the i3 parser (`Could not translate string to key symbol`). Fix: dedicated `scripts/screenshot.sh` script, and binding to `/usr/local/bin/aios-agent/scripts/screenshot.sh`.

## v0.14 - 2026-08-28 22:23

### agent: executes real tools (Carlos feedback)

- **`import sys` in `agent.py`**: `_out()` and `_cbreak_on()` used `sys` without importing it → `NameError` that the stream `except` swallowed silently (the agent seemed "mute"; on `shutdown` the error jumped). Root fix.
- **Tool visible before executing**: the `⚙ tool(...)` is shown BEFORE `execute_tool` — a long command no longer looks like "it does nothing".
- **`run_command` with correct stdin**: `/dev/null` by default (an interactive prompt no longer blocks silently) and auto-`y` for `sven install/upgrade/update` (the `:: Proceed? [Y/n]` no longer hangs).
- **Tool `list_desktop_apps`**: parses `/usr/share/applications/*.desktop` — the agent answers "what apps are there" by actually searching (e.g. Firefox), not from memory.
- **Grounding**: "sven always with sudo" + "never end the turn with I'll do it; emit the tool_call in the same turn" + "use list_desktop_apps".

### local LLM loading

- **Real progress bar** in `chat.py` `_start_local_model`: real phases from llama-server log (`loading model` → `init` → `model loaded` → `listening`) with percentage and time, instead of fixed 30s. If it doesn't start, it dumps the captured log.

### screenshots and diagnostics

- **Printscreen (`Print`)**: `scrot` to `~/screenshots/shot-<timestamp>.png`; documented in `shortcuts.txt` along with the chat commands `/think /health /reset /stats`.
- **`aios-diag`**: collects diagnostics (system + errors + AIOS logs + screenshots since last collection), redacts keys from `config.yaml`, compresses `tar.zst` with timestamp and uploads via rsync to a write-only `diag` account (rrsync, no shell/sudo). Key not included in ISO (`--local` = local only).

## v0.13 - 2026-08-28 08:47

### stability fixes (Arnold feedback / physical laptops)

- **Live→menu loop**: `_live_flow` returns `True` on completion and `main()` does `break` — before "Setup complete" did not finish and returned to the menu in a loop.
- **Internet with retry**: `_wait_internet()` waits for DHCP after associating WiFi before declaring "no internet" (before it was an immediate false negative).
- **Delete/arrows in `_read_line`**: handling of escape sequences (`\x1b`, Delete xterm/rxvt) in form inputs.
- **sven timeout 600s**: `run_command` gives a generous timeout to `sven install/upgrade/sync` (before it timed out after minutes).
- **Chat without staircase effect**: `_out()` writes explicit CRLF in LLM output (streaming, tools and final newline). Before it wrote a simple newline relying on tty ONLCR and the cursor didn't return to col 0 → each prompt shifted right.

## v0.12 - 2026-08-27 19:53

### ollama-hardened support (Moonlight) as provider

- **X-API-Key**: `auth_type` in config (bearer/x-api-key); `CLOUD_HEADERS` uses `X-API-Key` for hardened. `verify=False` only for x-api-key (self-signed cert).
- **Provider "Ollama Hardened"**: `https://webuillama.ccmai.org:8443/v1/chat/completions`, Moonlight-16B-A3B Q3_K_M. Key in `~/.aios/.env` (private, not in ISO).
- **Fix reading key** of custom provider (`provider_env`).
- **Hardened Caddyfile** (ollama-hardened repo): API routes → 401 without a valid key.

## v0.11 - 2026-08-27 19:23

### local LLM improvements (accuracy / anti-hallucination)

- **AIOS grounding**: `_AIOS_GROUNDING` injects AIOS invariants into the system prompt (LFS, `sven` as the only package manager — never apt/dnf/pacman, systemd, i3, networking with systemd-networkd + wpa_supplicant without ctrl_interface, usrmerge, `aios-update`/`aios-install`, recording `$mod+Print`). Prevents the model from inventing commands from other distros.
- **Verification discipline**: rule in prompt — for questions about the CURRENT state of the system (RAM/disk/processes/services), check with a tool first, never answer from memory.
- **Sampling per official Qwen3 doc**: `_sampling_params()` — thinking `temp 0.6/top_p 0.95/top_k 20/min_p 0`, no-thinking `0.7/0.8/20/0`; cloud keeps conservative temperature. A/B verified on VPS (b10655): same correct answer, no repetitions.
- **Reasoning_content echo**: the agent captures and returns `reasoning_content` in multi-turn history (clean thinking in long conversations).

## v0.10 - 2026-08-27 17:49

### local thinking switch (ON/OFF) + relative context/threads in disk installation

- **Local thinking mode (Qwen3-8B)**: binary ON/OFF switch via `local.think` key in `config.yaml` (default OFF).
  - `agent.py`: `THINK_LOCAL` (env `AIOS_LOCAL_THINK`) controls the `/no_think` token in the query, the "Do not use  thinking tags" system prompt rule and `max_tokens` (min. 2048 when thinking, because reasoning consumes tokens before the response). `_quick_llm` always uses `/no_think`.
  - `chat.py`: passes `AIOS_LOCAL_THINK` to the environment before importing `agent`.
  - `setup.py`: asks "Enable thinking mode? [y/N]" in live and install.
  - `aios-install`: new flag `--think 0|1`.
- **Empirically verified (VPS, llama.cpp b10655)**: with `/think`, Qwen3 reasoning goes in `delta.reasoning_content` (SEPARATE field), NOT inline in `delta.content`. The agent only reads `content`/`tool_calls`, so reasoning is neither printed nor contaminates the response; `_clean` remains as a safety net.
- **Fix context/threads in disk installation**: `aios-install` wrote hardcoded `threads: 14` and `context: 32768`; now uses `_detect_cpu()` and `_auto_context(_detect_ram_gb())` (mirror of `setup.py`), consistent with live and without launching llama-server with `-c 32768` on machines ≤8 GB.
- **Hot `/think` command**: thinking toggle without leaving the agent (like `/sound`); persists in `config.yaml` and `agent.set_think()` regenerates token + `max_tokens` + system prompt at runtime. Documented in `shortcuts.txt` (aios-lfs).

## v0.9 - 2026-08-04 23:23

### fix: mute agent (blank response + prompt >)

- **Symptom**: the agent stopped responding (blank response, prompt `>`, no tool execution) when the model returned long tool calls with vision coordinates (e.g. OCR TSV "805,316,5x3") and occasionally without them.
- **Root cause**: `chat.py` silently swallowed the return value of `agent.run()` (only `print()` newline) → any error or "(empty model response)" became invisible. Also, if the LLM stream was cut without finish_reason (server closed mid-tool-call), content was empty and the agent gave up without retrying.
- **Fixes**:
  1. `chat.py`: the return value of `agent.run()` is shown if it didn't come from the stream (errors and empty responses are no longer mute).
  2. `agent.py`: raw SSE stream log in `/tmp/aios-stream.log` (`data:` lines + END marker with finish_reason/chunks/tools + exceptions) for diagnostics.
  3. `agent.py`: single retry if the stream ends without finish_reason and without content ("⚠️ Empty stream (possible cut). Retrying...").
- Verified on physical laptop (4 Aug 2026): after restarting the agent, it responds normally. Pending long-term confirmation of the coordinates case.

## v0.8 - 2026-08-04 09:08

### distro kernel (#5) - generic hardware

- Kernel 6.18.10 config expanded: wifi (iwlwifi, ath9k/10k/11k, rtw88/89, rtl8xxxu, brcmfmac, rtlwifi/rtl8723be/rtl8821ae), DRM (i915/amdgpu/nouveau), NVMe, UAS, I2C_HID_ACPI, ethernet (r8169/e1000e/igb), ALSA HDA + USB audio (=m via udev; critical =y).
- linux-firmware firmware in /lib/firmware (~534MB) + iwlwifi symlinks (intel/iwlwifi -> root) + regulatory.db + rtl_nic.
- Verified on HP Notebook (AMD APU + Realtek RTL8723BE + RTL8106E): wifi, ethernet, audio (alc269 + HDMI), Synaptics touchpad.

### setup.py - option 5 WIFI SETUP

- New menu option: detects wifi interface, scans SSIDs, generates `/etc/wpa_supplicant/wpa_supplicant-<iface>.conf` (wpa_passphrase), connects with wpa_supplicant and verifies connectivity.
- Internet verification with urllib against example.com/archlinux.org: curl/ping don't exist on the system and 1.1.1.1 returns 403 to urllib.
- Persistence on installed system: enables wpa_supplicant@<iface> and creates `/etc/systemd/network/20-wifi-dhcp.network` (systemd-networkd DHCP on wl*, same mechanism as ethernet en*).
- Bug fix: the `aios-wifi.service` unit used `/usr/sbin/wpa_supplicant` (non-existent path; Arch installs it in /usr/bin) → 203/EXEC → wifi associated without IP at boot. Replaced by networkd.

### infrastructure and dependencies

- sven: database sync (`sven sync`) + manual JSON registry in `/var/lib/sven/installed/` for ghost-state packages (pcsclite, libinput, libgudev) — packages marked installed but missing files.
- libinput.so.10 + libgudev-1.0.so.0 + libwacom + liblua installed (dependency chain of the Xorg libinput driver) → Synaptics touchpad works on real hardware.
- busybox: applet symlinks (`/bin/udhcpc`, `/sbin/udhcpc`) + default.script in `/usr/share/udhcpc` and `/etc/udhcpc` (Ubuntu busybox looks for compiled path `/etc/udhcpc/`).
- MILESTONE: complete AIOS on real hardware - wifi at boot without cable, cloud agent works (4 Aug 2026).

## v0.7 - 2026-08-02 22:15

### physical milestone

- Full boot of AIOS LFS on real hardware (physical laptop with SATA SSD) verified on 2 Aug 2026.
- ISO boots from USB when written with Rufus in DD mode.
- Installer copies the system to SSD disk and the machine boots from disk with AIOS banner and login.
- Whole chain (live USB → install → disk boot) works on physical hardware, not only VirtualBox.
- Fixed the live initrd init to wait for the boot device to appear for 30 s, with verification loop `[ -b ]` and `break 2`.
- Expanded recognized device list in init: `sdc`, `sdd`, `hd*`, `nvme*`, `mmcblk*`.
- Replaced silent kernel panic with clear message `AIOS: boot media not found` plus busybox emergency shell.
- Documented that Rufus must be used in DD mode; ISO mode creates FAT32 and init looks for iso9660, so it currently fails.

### next steps

- Support Rufus ISO/FAT32 mode in the live initrd init script.
- Compile and integrate kernel #5 with NVMe and UAS support.

## v0.6 - 2026-08-02 18:51

### aios-install v1.1.2

- **Fix: kernel panic when booting AIOS LFS from hard disk.**
  The installed-to-disk system showed panic `'Attempted to kill init! exit code=0x7f00'` (127) right after boot.

#### root causes

1. **Octal escape in the `sed` pattern of `build_disk_initrd`**: the Python string used a single backslash in `'s/.*root=\([^ ]*\).*/\1/p'`. Python interprets `\1` as the SOH control character (`0x01`), which ended up written in the generated `init`. At runtime, `sed` returned a phantom root device and the subsequent `mount -t ext4` failed.
2. **Wrong fallback in initrd**: when `mount` failed, the script executed `exec /bin/sh`, but in the transformed live initrd `/bin/sh` doesn't exist; only `init` and `bin/busybox`, without applet symlinks. The `exec` failed with code 127, killing init and causing the panic.
3. **No wait for root device**: the root device might not be available at the instant init queried it, so even with the correct device the boot was unstable.

#### applied solution

- Fixed the sed/tail pattern using double backslash (`\\(` and `\\1`) so the generated `init` script receives literally `\(` and `\1`, and `sed` extracts the correct root device.
- Added an active wait loop of up to 30 seconds until the root device appears in `/dev`.
- Replaced the fallback `exec /bin/sh` with `exec /bin/busybox sh`, which exists in the initrd.
- Now uses `exec /bin/busybox switch_root /root /sbin/init` to continue boot of the real system.
- Added `/bin/busybox` (static, 2.1 MB, extracted from initrd) to the live system squashfs, since `build_disk_initrd` needs it and the live system didn't include it.

#### verification

- Reinstalling AIOS LFS to disk, boot from disk works correctly: the AIOS logo is shown and it reaches login.
- Pending polish: GRUB still shows the `'Welcome to GRUB!'` message. Future improvement: `timeout_style=hidden` and `quiet_boot=1`.

## v0.5 - 2026-08-02 14:34

### aios-install

- **v1.1.0**: allow changing the `root` and `aios` passwords during installation. Uses `getpass`, minimum length of 8 characters and `chpasswd` via chroot by stdin. The final summary omits `"Login: aios/aios"` if credentials were changed.
- **v1.1.1**: silent boot on disk. The generated `grub.cfg` uses `timeout=0`, `quiet`, `systemd.show_status=false`, `initrd /boot/initrd.img` and real `root=`. `build_disk_initrd` transforms the live initrd preserving the banner and replacing the ISO loop with `mount root` + `switch_root /sbin/init`.
- Removed `nokaslr` from the generated `grub.cfg`.
- `print_box` centered on screen.

## v0.4 - 2026-08-02 14:34

### setup.py

- `validate_api_key` runs the request in a daemon thread with `join(timeout=12)`; the `urlopen` timeout did not cover DNS resolution and the cloud menu hung indefinitely.
- At the end of `__main__`, `os._exit(0)` is used to force exit without waiting for residual threads.
- The API key is saved correctly in `~/.aios/.env` (fixed the bug `if not key:` → `if key:`).
- LOCAL menu updated with model `Qwen3-8B-Instruct` and text `"1) LOCAL (no internet) / Simple tasks"`.
- `print_box` centered on screen using `os.get_terminal_size`, with horizontal and vertical padding.
- Final setup message: `"Setup complete. Starting the AIOS agent..."`, reflecting the automatic step from setup to aios.

## v0.3 - 2026-07-26 21:28 — Fix bootloader GRUB on disk installations (VirtualBox)

- `aios-install`: dynamic GRUB menu generation (`grub-mkconfig`) replaced by a fixed text-mode `grub.cfg`.
- Motivation: `grub-mkconfig` generated a graphical menu (`load_video`, `insmod all_video`, `gfxpayload=keep`, `terminal_output gfxterm`, `menuentry "Arch GNU/Linux"`) that hung in VirtualBox showing `Loading Linux 6.18.10-lfs ...`.
- New `grub.cfg` generated by `install_grub()`:
  - `set default=0`
  - `set timeout=5`
  - `menuentry "AIOS LFS" { linux /boot/vmlinuz-6.18.10-lfs root=/dev/sda2 rw nokaslr console=tty0 loglevel=6 }`
- `grub-install` is kept to write the bootloader to the target disk.
- UUIDs and "Arch Linux" references removed from the boot menu.
- README.md updated with section "Fix v7: Graphical GRUB hangs in VirtualBox after disk installation".

## v0.2 - 2026-07-23 12:34 — SRE Agent with native function calling on Qwen2.5-7B-Instruct

- Definitive model fixed to Qwen2.5-7B-Instruct; discarded Qwen2.5-Coder-3B and other models <7B due to unreliable function calling.
- 13 tools: `run_command`, `read_file`, `write_file`, `web_search`, `git_operation`, `mcp_call`, `run_playbook`, `process_start`, `process_send`, `process_close`, `process_list`, `cloud_reasoning`, `get_context_usage`.
- Procedural Skill-Pro memory, context compression with real token counting via `/v1/tokenize`, persistent session and apt error recovery.
- Readline history, cursor navigation and Ctrl+C that interrupts the current turn without exiting the chat.
- Setup wizard (`setup.py`) with local/cloud/hybrid modes and 7 providers (DeepSeek V4 Flash/Pro, OpenAI, Anthropic, Google, Kimi, Ollama Cloud, OpenRouter); separate sessions and memory per mode; `context_limit` per provider in `data/config.yaml`.
- Automatic RAM detection from `/proc/meminfo` and automatic local context scaling: ≤8 GB → 8K, 12–16 GB → 32K, >16 GB → 64K.
- Automatic CPU thread allocation at 87.5% of cores (e.g. 14/16); menu shows `N/16 cores` instead of percentage.
- `cloud_reasoning` delegates complex reasoning to cloud with full local context; `get_context_usage` shows used tokens vs. maximum.
- Compression per mode: 95% of local context (32K default) for local/hybrid, 50% of `context_limit` for cloud.
- Anti-loop: if the same tool + arguments repeats ≥3 times, the user is asked whether to abort with a 10 s timeout.
- Fixes: Docker `--format` no longer flagged destructive; local/hybrid endpoint corrected to `/v1/chat/completions`; API key hidden with `getpass`; N/16 cores shown; DeepSeek updated to V4 Flash and V4 Pro; Ollama Cloud added as provider; `.gitignore` updated with `gcc*`; liability disclaimer in README; minimum local RAM raised from 8 GB to 12 GB.
- README.md and executive PDF updated.

## v0.1 - 2026-07-21 11:32 — SRE Agent with native function calling on Qwen3-8B

- Complete repository rewrite.
- Lightweight SRE agent with native function calling via llama.cpp server.
- New tools:
  - `run_command`: executes shell commands on Linux.
  - `read_file`: reads configuration files and logs.
  - `write_file`: writes files, blocking critical system paths.
- Conversational support in Spanish with up to 5 reasoning turns.
- Basic security: warning before destructive commands and blocking of `/etc`, `/boot`, `/sys`, `/proc`, `/dev`.
- Interactive CLI in `chat.py`.
- README.md and executive PDF in `docs/ejecutivo.pdf`.
