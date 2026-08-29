# Changelog

## v0.16 - August 2026

### voice (TTS/STT) — independent `voice:` section from chat

- **Config**: `voice:` section in `config.yaml` (tts/stt/tts_lang), separate from `cloud:` (chat). Setup (live and `aios-install`) lets choose TTS (off/espeak/gemini/openai), STT (off/vosk/gemini/openai) and language; voice keys go to `~/.aios/.env` apart from chat (`GOOGLE_API_KEY`/`OPENAI_API_KEY` vs `DEEPSEEK_API_KEY`).
- **TTS** (`voice.py`): local espeak-ng (no key), Gemini `gemini-2.5-flash-tts` and OpenAI `gpt-4o-mini-tts` (cloud). Skips code blocks/tables so it doesn't spell them out, and speaks in a thread (does not block chat). `espeak-ng` installed via sven.
- **STT** (`voice.py`): local vosk, Gemini and OpenAI cloud (records with `arecord`).
- **Commands**: `/voice` (toggles voice, persists) and `/mic` (records + transcribes + sends as message).
- **Icon**: `VOX/MIC` block in the i3 bar (green=active, dimmed=off) reading `data/voice_state.json`.

### fixes

- **Beep/tic did not sound**: `aplay --buffer-size=512 --period-size=512` (buffer == period) failed silently on some codecs; removed (device defaults). `aios-diag` now collects audio state (`aplay -l`, `/proc/asound/cards`, `amixer`, snd/hda errors).
- **Loading bar in English**: the LLM progress bar text was in Spanish; switched to English (consistent with the rest of the printf).

## v0.15 - August 2026

### fixes for LLM boot and screenshot (progress bar regression)

- **LLM loading stuck at 85%**: `_start_local_model` used `select` on raw fd + `readline` with Python buffer. When llama-server wrote `model loaded` and `listening` almost together, `readline` read both lines into buffer but returned only the first; `listening` stayed stuck in the buffer (select watches the fd, not the buffer) and the bar stayed at 85% forever **even though the server was already listening** (hence 0% CPU and "does not finish"). Fix: **reader thread + queue** (no select) that drains stdout and detects `listening` for real; 15 min timeout and dump of the last lines if it doesn't start.
- **Printscreen (`Print`)**: inline `scrot` in i3 with `%` (strftime) + `&&` + nested quotes broke the i3 parser (`Could not translate string to key symbol`). Fix: dedicated `scripts/screenshot.sh` script, and binding to `/usr/local/bin/aios-agent/scripts/screenshot.sh`.

## v0.14 - August 2026

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

## v0.13 - August 2026

### stability fixes (Arnold feedback / physical laptops)

- **Live→menu loop**: `_live_flow` returns `True` on completion and `main()` does `break` — before "Setup complete" did not finish and returned to the menu in a loop.
- **Internet with retry**: `_wait_internet()` waits for DHCP after associating WiFi before declaring "no internet" (before it was an immediate false negative).
- **Delete/arrows in `_read_line`**: handling of escape sequences (`\x1b`, Delete xterm/rxvt) in form inputs.
- **sven timeout 600s**: `run_command` gives a generous timeout to `sven install/upgrade/sync` (before it timed out after minutes).
- **Chat without staircase effect**: `_out()` writes explicit CRLF in LLM output (streaming, tools and final newline). Before it wrote a simple newline relying on tty ONLCR and the cursor didn't return to col 0 → each prompt shifted right.

## v0.12 - August 2026

### ollama-hardened support (Moonlight) as provider

- **X-API-Key**: `auth_type` in config (bearer/x-api-key); `CLOUD_HEADERS` uses `X-API-Key` for hardened. `verify=False` only for x-api-key (self-signed cert).
- **Provider "Ollama Hardened"**: `https://webuillama.ccmai.org:8443/v1/chat/completions`, Moonlight-16B-A3B Q3_K_M. Key in `~/.aios/.env` (private, not in ISO).
- **Fix reading key** of custom provider (`provider_env`).
- **Hardened Caddyfile** (ollama-hardened repo): API routes → 401 without a valid key.

## v0.11 - August 2026

### local LLM improvements (accuracy / anti-hallucination)

- **AIOS grounding**: `_AIOS_GROUNDING` injects AIOS invariants into the system prompt (LFS, `sven` as the only package manager — never apt/dnf/pacman, systemd, i3, networking with systemd-networkd + wpa_supplicant without ctrl_interface, usrmerge, `aios-update`/`aios-install`, recording `$mod+Print`). Prevents the model from inventing commands from other distros.
- **Verification discipline**: rule in prompt — for questions about the CURRENT state of the system (RAM/disk/processes/services), check with a tool first, never answer from memory.
- **Sampling per official Qwen3 doc**: `_sampling_params()` — thinking `temp 0.6/top_p 0.95/top_k 20/min_p 0`, no-thinking `0.7/0.8/20/0`; cloud keeps conservative temperature. A/B verified on VPS (b10655): same correct answer, no repetitions.
- **Reasoning_content echo**: the agent captures and returns `reasoning_content` in multi-turn history (clean thinking in long conversations).

## v0.10 - August 2026

### local thinking switch (ON/OFF) + relative context/threads in disk installation

- **Local thinking mode (Qwen3-8B)**: binary ON/OFF switch via `local.think` key in `config.yaml` (default OFF).
  - `agent.py`: `THINK_LOCAL` (env `AIOS_LOCAL_THINK`) controls the `/no_think` token in the query, the "Do not use <think> tags" system prompt rule and `max_tokens` (min. 2048 when thinking, because reasoning consumes tokens before the response). `_quick_llm` always uses `/no_think`.
  - `chat.py`: passes `AIOS_LOCAL_THINK` to the environment before importing `agent`.
  - `setup.py`: asks "Enable thinking mode? [y/N]" in live and install.
  - `aios-install`: new flag `--think 0|1`.
- **Empirically verified (VPS, llama.cpp b10655)**: with `/think`, Qwen3 reasoning goes in `delta.reasoning_content` (SEPARATE field), NOT inline in `delta.content`. The agent only reads `content`/`tool_calls`, so reasoning is neither printed nor contaminates the response; `_clean` remains as a safety net.
- **Fix context/threads in disk installation**: `aios-install` wrote hardcoded `threads: 14` and `context: 32768`; now uses `_detect_cpu()` and `_auto_context(_detect_ram_gb())` (mirror of `setup.py`), consistent with live and without launching llama-server with `-c 32768` on machines ≤8 GB.
- **Hot `/think` command**: thinking toggle without leaving the agent (like `/sound`); persists in `config.yaml` and `agent.set_think()` regenerates token + `max_tokens` + system prompt at runtime. Documented in `shortcuts.txt` (aios-lfs).

## v0.9 - August 2026

### fix: mute agent (blank response + prompt >)

- **Symptom**: the agent stopped responding (blank response, prompt `>`, no tool execution) when the model returned long tool calls with vision coordinates (e.g. OCR TSV "805,316,5x3") and occasionally without them.
- **Root cause**: `chat.py` silently swallowed the return value of `agent.run()` (only `print()` newline) → any error or "(empty model response)" became invisible. Also, if the LLM stream was cut without finish_reason (server closed mid-tool-call), content was empty and the agent gave up without retrying.
- **Fixes**:
  1. `chat.py`: the return value of `agent.run()` is shown if it didn't come from the stream (errors and empty responses are no longer mute).
  2. `agent.py`: raw SSE stream log in `/tmp/aios-stream.log` (`data:` lines + END marker with finish_reason/chunks/tools + exceptions) for diagnostics.
  3. `agent.py`: single retry if the stream ends without finish_reason and without content ("⚠️ Empty stream (possible cut). Retrying...").
- Verified on physical laptop (4 Aug 2026): after restarting the agent, it responds normally. Pending long-term confirmation of the coordinates case.

## v0.8 - August 2026

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

## v0.7 - August 2026

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

## v0.6 - August 2026

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

## v0.5 - August 2026

### aios-install

- **v1.1.0**: allow changing the `root` and `aios` passwords during installation. Uses `getpass`, minimum length of 8 characters and `chpasswd` via chroot by stdin. The final summary omits `"Login: aios/aios"` if credentials were changed.
- **v1.1.1**: silent boot on disk. The generated `grub.cfg` uses `timeout=0`, `quiet`, `systemd.show_status=false`, `initrd /boot/initrd.img` and real `root=`. `build_disk_initrd` transforms the live initrd preserving the banner and replacing the ISO loop with `mount root` + `switch_root /sbin/init`.
- Removed `nokaslr` from the generated `grub.cfg`.
- `print_box` centered on screen.

## v0.4 - August 2026

### setup.py

- `validate_api_key` runs the request in a daemon thread with `join(timeout=12)`; the `urlopen` timeout did not cover DNS resolution and the cloud menu hung indefinitely.
- At the end of `__main__`, `os._exit(0)` is used to force exit without waiting for residual threads.
- The API key is saved correctly in `~/.aios/.env` (fixed the bug `if not key:` → `if key:`).
- LOCAL menu updated with model `Qwen3-8B-Instruct` and text `"1) LOCAL (no internet) / Simple tasks"`.
- `print_box` centered on screen using `os.get_terminal_size`, with horizontal and vertical padding.
- Final setup message: `"Setup complete. Starting the AIOS agent..."`, reflecting the automatic step from setup to aios.

## v0.3 — Fix bootloader GRUB on disk installations (VirtualBox)

- `aios-install`: dynamic GRUB menu generation (`grub-mkconfig`) replaced by a fixed text-mode `grub.cfg`.
- Motivation: `grub-mkconfig` generated a graphical menu (`load_video`, `insmod all_video`, `gfxpayload=keep`, `terminal_output gfxterm`, `menuentry "Arch GNU/Linux"`) that hung in VirtualBox showing `Loading Linux 6.18.10-lfs ...`.
- New `grub.cfg` generated by `install_grub()`:
  - `set default=0`
  - `set timeout=5`
  - `menuentry "AIOS LFS" { linux /boot/vmlinuz-6.18.10-lfs root=/dev/sda2 rw nokaslr console=tty0 loglevel=6 }`
- `grub-install` is kept to write the bootloader to the target disk.
- UUIDs and "Arch Linux" references removed from the boot menu.
- README.md updated with section "Fix v7: Graphical GRUB hangs in VirtualBox after disk installation".

## v0.2 — SRE Agent with native function calling on Qwen2.5-7B-Instruct

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

## v0.1 — SRE Agent with native function calling on Qwen3-8B

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
