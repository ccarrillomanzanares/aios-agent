# aios-agent v2.2 — SRE Agent with native function calling

**⚠️ DISCLAIMER**
This software is provided as is, without warranty of any kind, express or implied.
The authors and contributors assume no responsibility or liability for any damages,
data loss, system failures, or other consequences arising from the use of this agent.

This agent executes shell commands and modifies system files. Improper use,
misconfiguration, or unexpected model behavior may result in:
- Data loss or corruption
- Service disruption
- Security vulnerabilities
- Unauthorized system changes

**You are solely responsible for:**
- Reviewing actions before confirmation
- Testing in a safe environment before production use
- Configuring appropriate security measures
- Understanding the capabilities and limitations of the LLM model in use

By using this software, you accept these terms and assume all risk.

---

A lightweight Site Reliability Engineering (SRE) agent that uses **native function calling** on top of the local **Qwen** model (served by llama.cpp). It can run Linux commands, read configuration/log files, write controlled changes, search the web, run playbooks, manage interactive processes, and interact with Git — all through a conversation.

## What does it do?

- Answers sysadmin questions in English, Spanish or Chinese.
- Executes shell commands on the local machine (`run_command`).
- Reads configuration files and logs (`read_file`).
- Writes files to allowed paths, blocking system directories (`write_file`).
- Searches the web via local Firecrawl (`web_search`).
- Interacts with Git repositories (`git_operation`).
- Calls external tools through MCP (`mcp_call`).
- Runs YAML playbooks sequentially (`run_playbook`).
- Starts, sends input to, and closes interactive processes (`process_start`, `process_send`, `process_close`, `process_list`).
- Offloads complex reasoning to a cloud model in hybrid mode (`cloud_reasoning`).
- Reports current context usage (`get_context_usage`).
- Maintains conversational context and performs up to 10 reasoning turns of tool→LLM.
- Plans and executes multi-step tasks without intermediate human intervention.
- Learns from repeated procedural queries through lightweight procedural memory (Skill-Pro pattern).

## Architecture

```
┌─────────────┐     HTTP JSON     ┌──────────────────┐
│  chat.py    │ ────────────────▶ │   agent.py       │
│ (CLI loop)  │                   │  orchestrator    │
│  + setup.py │                   │  function calls  │
└─────────────┘                   │  + memory        │
                                  └────────┬─────────┘
                                           │ tools schema
                                           ▼
                                  ┌──────────────────┐
                                  │    tools.py      │
                                  │ run_command      │
                                  │ read_file        │
                                  │ write_file       │
                                  │ web_search       │
                                  │ git_operation    │
                                  │ mcp_call         │
                                  │ run_playbook     │
                                  │ process_*        │
                                  └──────────────────┘
                                           │
                                           ▼
                                  ┌──────────────────┐
                                  │ Qwen3-8B / Qwen2.5-7B-Instruct via     │
                                  │ llama.cpp :8083  │
                                  └──────────────────┘
```

- `setup.py`: first-run configuration wizard (local / cloud / hybrid) with per-mode sessions and memory.
- `chat.py`: interactive loop with readline history and slash commands.
- `agent.py`: manages messages, calls the LLM, executes tool calls, and maintains procedural memory.
- `tools.py`: tool definitions and handlers.
- `memory.py`: Skill-Pro procedural memory.
- `playbook.py`: YAML playbook runner.
- `process.py`: interactive process management with PTY.
- `scripts/launch_llama.py`: systemd-compatible launcher for llama-server.
- `scripts/firstboot.sh`: one-time ISO first-boot setup wizard.
- `systemd/aios-llama.service`: systemd unit that keeps the model server alive.
- `systemd/aios-agent.service`: systemd unit that starts the chat UI after the model server is ready.

## Setup Wizard

The first time the agent starts, `setup.py` presents a text-menu installer that lets you choose the operating mode without editing configuration files by hand.

### Available modes

1. **LOCAL** — Uses the bundled **Qwen** model served by llama.cpp on `http://localhost:8083`. Requires at least 8 GB RAM. This is the default for an offline ISO deployment.
2. **CLOUD** — Select a provider (DeepSeek, OpenAI, Anthropic, Google Gemini, Moonshot/Kimi, Ollama Cloud, OpenRouter) and enter the API key. The agent will route all LLM calls to the chosen cloud endpoint.
3. **HYBRID** — The local model acts as the orchestrator; complex or multi-step reasoning is offloaded to the configured cloud provider through the dedicated `cloud_reasoning` tool.

### What the wizard configures

- Operating mode (`local`, `cloud`, or `hybrid`).
- Cloud provider and model (only for cloud/hybrid modes). Provider-specific `context_limit` is stored in `~/.aios/config.yaml`.
- API key stored in `~/.aios/.env`. `~/.aios/.env` is never committed to Git (`.gitignore`).
- Local model selection from the menu:
  - **Qwen3-8B (default)** — most reliable for function calling.
  - **Qwen2.5-7B-Instruct** — faster alternative.
  - The selected GGUF is downloaded automatically from HuggingFace if it is not present in `~/models`.
- CPU auto-allocation: reserves one core for the OS and assigns the rest to llama.cpp (e.g. 14/16 cores, 87.5% utilization); the menu shows actual cores used (`N/16 cores`) rather than a percentage.
- RAM auto-detection from `/proc/meminfo` and auto-scaled local context:
  - ≤8 GB RAM → 8K context
  - 12–16 GB RAM → 32K context
  - >16 GB RAM → 64K context
- Detection banner shown during setup: `Detected: 14 CPU threads, 62 GB RAM -> 64K context`.

Configuration is written to `~/.aios/config.yaml` and read automatically on subsequent runs. Run `python3 setup.py` again at any time to reconfigure.

## ISO Integration

The repository includes systemd units and a first-boot script so the agent can be shipped as a bootable ISO image that starts automatically on power-on.

### Files

| File | Purpose |
|------|---------|
| `systemd/aios-llama.service` | Starts `llama-server` for the configured local model via `scripts/launch_llama.py`. |
| `systemd/aios-agent.service` | Waits until `http://127.0.0.1:8083/health` responds and then launches `chat.py`. |
| `scripts/launch_llama.py` | Reads `~/.aios/config.yaml`, resolves the model path, builds the `llama-server` command line and `exec`s it. |
| `scripts/firstboot.sh` | One-time first-boot wizard. Runs `setup.py`, enables the systemd units and starts them if the model is already downloaded. |

### Service behavior

- `aios-llama.service` is ordered **after** `network-online.target` and restarts on failure.
- `aios-agent.service` **requires** `aios-llama.service`; it blocks with a `curl` health check loop until the local model server is ready.
- Both services run as the `aios` user and expect the code to be installed at `/usr/local/bin/aios-agent`.
- The UI, prompts and exit messages are all in English so the ISO behaves consistently regardless of the host locale.

### Install for ISO

```bash
sudo cp systemd/aios-llama.service /etc/systemd/system/
sudo cp systemd/aios-agent.service  /etc/systemd/system/
sudo cp scripts/firstboot.sh        /usr/local/bin/aios-firstboot
sudo chmod +x /usr/local/bin/aios-firstboot
sudo systemctl daemon-reload
# firstboot.sh is run once during the first boot
```

## API Keys

Cloud and hybrid modes need an API key. Since commit `a2d989d` keys are no longer stored inside `config.yaml`:

- `setup.py` writes the key to `~/.aios/.env`.
- `.env` is listed in `.gitignore` so it is never committed.
- `chat.py` loads `.env` automatically on startup and exposes it to `agent.py`/`tools.py` through environment variables.
- The mapping between provider and environment variable is kept in `chat.py` (`CLOUD_ENV_VARS`).
- The key prompt in the wizard is visible (not hidden with `getpass`) so it works when pasted via clipboard inside a terminal.
- If the user leaves the API key empty in cloud/hybrid mode the agent falls back gracefully to local mode.

## Model

The default local model is **Qwen3-8B** because it is the most reliable option evaluated for native function calling. **Qwen2.5-7B-Instruct** remains available as a faster alternative.

- Production service points to `:8083`.
- Native function calling is the core mechanism of the agent; reliability is more important than raw speed.
- Models smaller than 7B were evaluated and discarded because they could not produce valid tool calls consistently for sysadmin tasks.

### Model selection

| Model | Default | Characteristics |
|-------|---------|-----------------|
| Qwen3-8B Q4_K_M | ✅ Yes | Most reliable native tool calls; auto-downloaded from HuggingFace. |
| Qwen2.5-7B-Instruct Q4_K_M | Optional | Faster; use when speed matters more than absolute tool-call reliability. |

### Model quantization

The deployed instance uses a single quantization that balances tool-calling quality, context budget, and speed on a modest VPS.

| Quantization | Speed (tok/s) | RAM/VRAM | Observed quality | Use case |
|--------------|---------------|----------|------------------|----------|
| Q4_K_M       | 57 prompt / 20 gen | 4.7 GB   | Reference        | Production server with enough memory |

The current deployed instance uses **Qwen2.5-7B-Instruct-Q4_K_M** at `:8083` with an 8K context window (`-c 8192`) and keeps ~95% of it for history (~7782 tokens). The server is started with `--jinja` for correct chat-template handling and `-t 14` on a 16-core host. To avoid silent context overflow, `agent.py` counts tokens with the real `/v1/tokenize` endpoint before compressing or truncating history, rather than estimating with a fixed chars-per-token ratio.

### Evaluated and discarded models

We tested several smaller and alternative models looking for a reliable <8B option. None matched the function-calling reliability of Qwen2.5-7B-Instruct.

| Model | Size | tok/s | Function calling | Verdict |
|-------|------|-------|------------------|---------|
| Qwen3-8B Q3_K_M | 3.9 GB | 14.9 | Works | Discarded — slower than Qwen2.5-7B Q4_K_M |
| Qwen3-4B (+jinja) | 2.4 GB | 42 | Inconsistent | Discarded — responds from memory, skips tools |
| Qwen2.5-Coder-3B | 1.8 GB | ~33 | Fails | Discarded — responds from memory, does not use tools |
| Phi-4-Mini 3.8B | 2.4 GB | 46 | Fails | Discarded — refuses to execute commands, aligned for safety |
| Llama-3.2-3B | 1.9 GB | 37 | Fails | Discarded — hallucinates tool calls with fake paths |
| Gemma-3-4B-IT | 2.4 GB | 16 | Fails | Discarded — hallucinates tool calls |

Conclusion: **models <7B are not reliable for function calling in sysadmin tasks.** Qwen3-8B and Qwen2.5-7B-Instruct are the CPU sweet spots for this agent.

## Readline history and Ctrl+C

The interactive CLI uses Python's `readline` module for standard terminal line editing:

- **Up / Down arrows**: browse previous commands entered in the current session and across sessions.
- **Left / Right arrows**: move the cursor to edit the current line.
- **Persistent history**: commands are saved to `data/.chat_history` and reloaded on startup (up to 500 entries).
- **Ctrl+C during a turn**: cancels the current LLM/tool-call turn and returns to the `> ` prompt without exiting the chat. This is handled with a `try/except KeyboardInterrupt` around `agent.run()` rather than a global signal handler.
- Ctrl+C at the main `input()` prompt still exits the chat as before.

## Per-mode sessions and memory

Each operating mode keeps its own session and procedural-memory cache, so context is never shared between local, cloud, and hybrid runs:

- Sessions: `data/session_local.json`, `data/session_cloud.json`, `data/session_hybrid.json`
- Skill-Pro cache: `data/skills_memory_local.json`, `data/skills_memory_cloud.json`, `data/skills_memory_hybrid.json`

On startup the chat prints: *"Independent session (context not shared across modes)"*.

### Context compression by mode

| Mode | Context window | History kept | Compression |
|------|----------------|--------------|-------------|
| LOCAL | 32768 tokens (default) | ~31129 tokens (95%) | Sliding-window + token-counting via `/v1/tokenize` |
| CLOUD | Provider `context_limit` | 50% of `context_limit` | Token-counting via provider tokenizer |
| HYBRID | 32768 tokens (local) | ~31129 tokens (95%) | Local compression; `cloud_reasoning` decides when to offload |

Session files are separated by mode (`data/session_local.json`, `data/session_cloud.json`, `data/session_hybrid.json`) and procedural-memory caches likewise (`data/skills_memory_local.json`, `data/skills_memory_cloud.json`, `data/skills_memory_hybrid.json`).

## Recent fixes

- `get_context_usage`: removed an undefined reference to `MAX_HISTORY_TOKENS`.
- Empty API key in cloud/hybrid mode now falls back to local mode gracefully.
- Anti-loop detection: if the same tool with the same arguments is invoked ≥3 times consecutively the agent asks whether to abort.
- Language support note updated: EN, ZH and ES are tested; other languages are not guaranteed.
- RAM auto-detect with context scaling now works correctly during the wizard.
- Setup wizard is fully in English for consistent ISO behavior.
- Visible API-key input for paste compatibility (no `getpass`).

## Roadmap

Features implemented in v2.2 (all completed):

- ✅ Native function calling over llama.cpp server (`/v1/chat/completions`)
- ✅ 13 tools: `run_command`, `read_file`, `write_file`, `web_search`, `git_operation`, `mcp_call`, `run_playbook`, `process_start`, `process_send`, `process_close`, `process_list`, `cloud_reasoning`, `get_context_usage`
- ✅ Conversational loop with up to 10 tool→LLM turns and persistent session context
- ✅ Multi-step planning and execution without intermediate human intervention
- ✅ Procedural memory / Skill-Pro pattern for repeated queries
- ✅ Real token-counting context compression via `/v1/tokenize`
- ✅ Error recovery: retries with `apt-get` when `apt` fails, handles apt locks
- ✅ Persistent session across restarts (`data/session.json`)
- ✅ Readline history and cursor navigation in the CLI
- ✅ Ctrl+C to interrupt the current turn without exiting
- ✅ Setup wizard: local / cloud / hybrid mode, provider selection, API key, CPU auto-allocation, model selection, auto-download
- ✅ Security (OWASP AI Agent cheat sheet): tool allowlist, human-in-the-loop for destructive commands, input validation, audit log (`audit.jsonl`)
- ✅ ISO integration: systemd units + firstboot + launch wrapper
- ✅ API-key isolation in `~/.aios/.env`
- ✅ Complete README.md with architecture, usage, security, ISO integration, and model evaluation
- ✅ Executive documentation in PDF (`docs/ejecutivo.pdf`)

## Multi-step planning

For complex tasks the agent does not perform a single function call: it first **thinks**, decomposes, and then executes the steps sequentially.

### How it works

1. **Planning prompt**: the system prompt instructs the LLM to generate a numbered plan of steps and keep executing it with the instruction `EJECUTA without explaining`.
2. **`MAX_TURNS=10`**: the function-calling loop allows up to 10 turns, enough for multi-step tasks.
3. **Sequential execution**: each tool call is performed, its result is injected into context, and the LLM decides the next step until the task finishes or the turn budget runs out.
4. **No intermediate human intervention**: the model executes directly; the user only receives the final summarized result. If the model detects a destructive or critical step, it asks for confirmation before continuing.

### Example execution

**User**: `install WordPress with Docker and MariaDB`

```text
Step 1: Verify Docker is installed and running.
Step 2: Create Docker network and MariaDB container with environment variables.
Step 3: Start WordPress container linked to MariaDB.
Step 4: Show final container and exposed port status.
```

The agent executes each step via `run_command`, receives the output, and advances automatically. At the end it responds with a summary of what was done.

## Cloud reasoning tool

`cloud_reasoning` (tool #12) is only used in hybrid mode. When the local orchestrator decides a query needs deeper reasoning, it sends the user prompt plus the last 10 messages of local context to the configured cloud endpoint.

- Environment: `AIOS_CLOUD_ENDPOINT` and `AIOS_API_KEY` (set by the setup wizard via `~/.aios/.env`).
- Timeout: 120 seconds.
- Temperature: 0.3.
- Use case: complex multi-step plans, code review, or analysis that exceeds the local 7B model's capacity.

`get_context_usage` (tool #13) returns tokens used vs. the configured context maximum, helping monitor session growth.

## Requirements

- Python 3.10+
- `requests` (`pip install requests`)
- `pyyaml` (`pip install pyyaml`)
- llama.cpp server running a supported Qwen model at `http://localhost:8083/v1/chat/completions` (local / hybrid mode)
- Cloud API key (cloud / hybrid mode)

## Usage

First run (or reconfiguration):

```bash
python3 setup.py
```

Interactive chat:

```bash
python3 chat.py
```

Example queries:

```text
> show disk usage
> read /var/log/syslog
> write a backup script at /tmp/backup.sh
> restart nginx
```

Type `exit`, `quit` or `salir` to finish.

## Security

- **Tool allowlist**: commands such as `rm -rf /`, `dd` to block devices, `mkfs.*`, `fdisk`, and `chmod 000` are rejected.
- **Human-in-the-loop**: destructive commands (`rm`, `sudo rm`, `> /dev/sd*`, `format`, `dd`) require explicit confirmation (default N, 10-second timeout).
- **Input validation**: control characters sanitized, 1000-character limit, system-prompt injection detected; rejected inputs are logged to `audit.jsonl`.
- **Path protection**: `write_file` blocks `/etc`, `/boot`, `/sys`, `/proc`, `/dev`.
- **Audit log**: every tool invocation and rejection is recorded in `audit.jsonl`.
- Full analysis in `SECURITY.md`.

## Files

- `setup.py` — first-run configuration wizard.
- `chat.py` — terminal chat interface with readline history and slash commands.
- `agent.py` — function-calling orchestrator and procedural memory.
- `tools.py` — shell, file, web, git, MCP, playbook, and process tools.
- `memory.py` — Skill-Pro procedural memory cache.
- `playbook.py` — YAML playbook runner.
- `process.py` — interactive process management with PTY.
- `scripts/launch_llama.py` — systemd-compatible llama-server launcher.
- `scripts/firstboot.sh` — ISO first-boot setup wizard.
- `systemd/aios-llama.service` — systemd unit for the model server.
- `systemd/aios-agent.service` — systemd unit for the chat UI.
- `README.md` — this document.
- `CHANGELOG.md` — change history.
- `SECURITY.md` — OWASP security analysis.
- `docs/ejecutivo.md` — executive summary in Markdown.
- `docs/ejecutivo.pdf` — executive summary in PDF.

## Project history

### Week 1 — RAG + hybrid approach

- Started with **Qwen3-0.6B** + ChromaDB (`e5-large` embeddings) + a procedural corpus of **955 documents**.
- Test battery: only **7/43 PASS (16%)**.
- Attempted fine-tune of the 0.6B model on an SRE dataset of 500 examples via Unsloth on a Lambda GPU.
- Fine-tune failed due to version incompatibilities (`trl`, `transformers`).
- The RAG approach was abandoned as fragile and expensive.

### Week 2 — Reset: pure function calling

- Deleted the hybrid projects (~10 GB) and started from scratch.
- Compiled **llama.cpp** for CPU with `-j16`.
- Downloaded **Qwen3-8B** (bartowski instruct GGUF).
- Built an agent in 3 files (~200 lines) with native function calling.
- Initial tools: `run_command`, `read_file`, `write_file`.
- The agent worked at **17 tok/s**.

### Week 3 — Feature layers

- Procedural memory (Skill-Pro, ICML 2026): JSON cache for repetitive responses.
- Multi-step planning: prompt with `EJECUTA without explaining`.
- Context compression: real token counting via `/v1/tokenize`.
- Error recovery: retries with `apt-get` when `apt` fails and handles apt locks.
- Persistent session (`data/session.json`) + readline history (`data/.chat_history`).
- Audit log (`audit.jsonl`).

### Week 3 — Advanced tools

- `web_search` via local Firecrawl.
- `git_operation` (status, commit, push, diff, log).
- `mcp_call` (connect external APIs via MCP).
- `run_playbook` (execute YAML sequentially).
- `process_start` / `send` / `close` / `list` (interactive processes with PTY).

### Week 3 — Security (OWASP)

- Tool allowlist: blocks `rm -rf /`, `dd`, `mkfs`, `fdisk`, `chmod 000`, etc.
- Human-in-the-loop: destructive commands ask for confirmation.
- Input validation: sanitized input, 1000 char limit, anti-injection.
- Created `SECURITY.md` with a full OWASP analysis.

### Week 4 — Model evaluation and setup wizard

- Tested several models <8B. All failed to produce reliable function calls for sysadmin tasks.
- **Qwen2.5-7B-Instruct Q4_K_M** chosen as the definitive model.
- Added `setup.py` wizard: local/cloud/hybrid mode, provider selection, API key, CPU auto-allocation.
- Added Ctrl+C interrupt for the current turn.

### Week 5 — ISO integration and reliability fixes

- Added `systemd/` units (`aios-llama.service`, `aios-agent.service`).
- Added `scripts/launch_llama.py` wrapper that reads `~/.aios/config.yaml` and execs `llama-server`.
- Added `scripts/firstboot.sh` one-time ISO setup wizard.
- Moved API keys out of `config.yaml` into `~/.aios/.env` (`.gitignore`).
- Added local model selection (Qwen3-8B default, Qwen2.5-7B optional) with HuggingFace auto-download.
- Fixed `get_context_usage` undefined `MAX_HISTORY_TOKENS` reference.
- Empty API key now falls back to local mode gracefully.
- Added anti-loop guard (≥3 repeated tool calls).
- Updated language support note (EN/ZH/ES tested).
- Setup wizard fully in English for consistent ISO UI.
- Visible API-key input for paste compatibility.

## Final state

- Model: **Qwen3-8B Q4_K_M** (default) or **Qwen2.5-7B-Instruct Q4_K_M** (optional)
- Server: llama.cpp at `:8083`, `--jinja`, `-c 8192`, `-t 14`
- Speed: **57/20 tok/s** prompt/gen
- Tools: `run_command`, `read_file`, `write_file`, `web_search`, `git_operation`, `mcp_call`, `run_playbook`, `process_start`, `process_send`, `process_close`, `process_list`, `cloud_reasoning`, `get_context_usage`
- Memory: procedural Skill-Pro cache
- Modes: local / cloud / hybrid (configured by `setup.py`)
- ISO: systemd units + firstboot + launch wrapper
- Security: OWASP tool allowlist, human-in-the-loop, input validation, audit log
- Repo: [github.com/ccarrillomanzanares/aios-agent](https://github.com/ccarrillomanzanares/aios-agent)

## Version history

### v2.2 — SRE Agent with ISO integration and Qwen3-8B default

- Default local model changed to **Qwen3-8B** with auto-download from HuggingFace; Qwen2.5-7B-Instruct remains available.
- API keys moved from `config.yaml` to `~/.aios/.env` (`.gitignore`); `chat.py` loads `.env` automatically.
- Visible API-key input for paste compatibility.
- ISO integration: `systemd/aios-llama.service`, `systemd/aios-agent.service`, `scripts/launch_llama.py`, `scripts/firstboot.sh`.
- `launch_llama.py` reads `~/.aios/config.yaml` and launches llama-server with the correct model, context, threads and `--jinja`.
- `aios-agent.service` waits for `http://127.0.0.1:8083/health` before starting the chat UI.
- Setup wizard fully in English; language support note updated to EN/ZH/ES tested.
- Anti-loop guard: abort prompt after ≥3 repeated identical tool calls.
- Graceful fallback to local mode when API key is empty.
- Fixed `get_context_usage` undefined `MAX_HISTORY_TOKENS` reference.
- README.md and `docs/ejecutivo.pdf` regenerated.

### v2.1 — SRE Agent with native function calling on Qwen2.5-7B-Instruct

- Definitive model set to Qwen2.5-7B-Instruct; Qwen2.5-Coder-3B and other <7B models evaluated and discarded due to unreliable function calling.
- 13 tools implemented: shell, file, web, git, MCP, playbook, interactive process management, cloud reasoning delegation, and context-usage monitoring.
- Procedural memory (Skill-Pro), real token-counting compression, persistent session, and error recovery.
- Readline history, cursor navigation, and Ctrl+C turn interrupt in the interactive CLI (`chat.py`).
- Setup wizard (`setup.py`) for local/cloud/hybrid mode with 7 providers (DeepSeek V4 Flash/Pro, OpenAI, Anthropic, Google, Kimi, Ollama Cloud, OpenRouter), per-mode sessions, per-mode memory, and provider-specific `context_limit` stored in `data/config.yaml`.
- RAM auto-detection in setup with auto-scaled local context: ≤8 GB → 8K, 12–16 GB → 32K, >16 GB → 64K.
- CPU auto-allocation adjusted to 87.5% (14/16 cores on typical hardware); menu shows `N/16 cores` instead of a percentage.
- 12th tool `cloud_reasoning` and 13th tool `get_context_usage`: cloud delegation and context-usage monitoring.
- Context compression tuned per mode: 95% of 32K default for local/hybrid, 50% of provider limit for cloud; sessions and procedural caches are separated by mode.
- Anti-loop guard: if the same tool + arguments repeats ≥3 times, the agent asks whether to abort with a 10-second timeout.
- Corrections: Docker `--format` no longer flagged as destructive, local endpoint fixed to `/v1/chat/completions`, API key hidden via `getpass`, CPU display shows actual cores (e.g. 14/16), DeepSeek models updated to V4 Flash and V4 Pro, Ollama Cloud added as provider, `.gitignore` updated with `gcc*`, minimum local RAM raised from 8 GB to 12 GB, liability disclaimer added to README.
- OWASP-aligned security: tool allowlist, human-in-the-loop, input validation, audit log.
- README and executive PDF regenerated.

### v2.0 — SRE Agent with native function calling on Qwen2.5-7B-Instruct

- Complete repository rewrite.
- Lightweight SRE agent with native function calling via llama.cpp server.
- New tools:
  - `run_command`: execute Linux shell commands.
  - `read_file`: read configuration and log files.
  - `write_file`: write files, blocking critical system paths.
- Spanish conversational support with up to 5 reasoning turns.
- Multi-step planning and execution without intermediate intervention.
- Basic security: warning before destructive commands and blocking of `/etc`, `/boot`, `/sys`, `/proc`, `/dev`.
- Interactive CLI in `chat.py`.
- Complete README.md with roadmap of implemented features.
- Executive PDF v2.0 in `docs/ejecutivo.pdf`.

## License

MIT / Internal use.
