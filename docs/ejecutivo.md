# Executive Summary — aios-agent

## Purpose

`aios-agent` is a lightweight SRE (Site Reliability Engineering) assistant that uses **native function calling** on a local Qwen model served by llama.cpp. It operates 100% offline in local mode, with an option for cloud models in cloud/hybrid mode. It runs Linux commands, reads and writes files, manages interactive processes, consults the web and learns from experience through procedural memory.

## Main components

| File | Function |
|---------|---------|
| `agent.py` | Function calling orchestrator, context compression and persistent sessions. |
| `tools.py` | Tool definitions and handlers (shell, read, write, web, git, MCP, processes). |
| `chat.py` | Interactive loop, config loading and mode selection. |
| `memory.py` | Persistent procedural memory per mode (ProcMEM). |
| `process.py` | Interactive process management via PTY. |
| `setup.py` | Initial configuration wizard (local/cloud/hybrid). |
| `aios-install` | Installer of the AIOS LFS ISO to hard disk. |
| `scripts/launch_llama.py` | llama-server launcher; does not create config, only starts in local/hybrid. |
| `scripts/firstboot.sh` | First-boot configuration. |
| `systemd/aios-llama.service` | systemd service for the model server (disabled at boot). |
| `systemd/aios-agent.service` | systemd service for the interactive agent (disabled). |

## What's new

1. **Standard system paths**
   - Server: `/usr/local/bin/llama-server`
   - Models: `/usr/local/share/aios/models/`
   - Agent code: `/usr/local/bin/aios-agent/`
   - Configuration: `~/.aios/config.yaml`
   - API keys: `~/.aios/.env`

2. **Install-to-disk (`aios-install`)**
   - GPT partitioning, ext4 formatting and copies the live system.
   - Installs GRUB, generates `/etc/fstab` by UUID.
   - Generates `~/.aios/config.yaml` for the `aios` user.

3. **Refined systemd (lazy start)**
   - `aios-llama.service`: disabled at boot; `setup.py` enables and starts it only if the chosen mode is `local` or `hybrid`.
   - `aios-agent.service`: disabled by default because it requires an interactive terminal.
   - `sshd`: disabled in the ISO, with no fixed host keys; start it manually if remote access is required.

4. **Passive launch_llama.py**
   - Does not create `~/.aios/config.yaml` by default.
   - Exits cleanly with code 0 if no config exists or if mode is `cloud`.
   - Starts the server only when `mode` is `local` or `hybrid`.

5. **Reference to AIOS LFS**
   - This agent is included in the `aios-lfs` ISO: https://github.com/ccarrillomanzanares/aios-lfs.

## Security

- Blocking of dangerous commands (`rm -rf /`, `dd`, `mkfs`, `fdisk`).
- Interactive confirmation for destructive commands.
- Write blocking on critical system paths.
- Restrictions on git operations (no `reset`, `rebase`, `merge`, `stash`, or branch deletion).

## Requirements and deployment

- Python 3.10+, `requests`, `pyyaml`.
- llama.cpp server at `127.0.0.1:8083` for local/hybrid mode.
- To install to disk: run `aios-install` from the AIOS LFS live environment.

## Project status

- Current version: **v0.16**
- Branch: `main`
- Last updated: July 24, 2026
- Repository: https://github.com/ccarrillomanzanares/aios-agent
