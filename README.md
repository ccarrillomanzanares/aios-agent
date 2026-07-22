# aios-agent v2.1 — SRE Agent with native function calling

A lightweight Site Reliability Engineering (SRE) agent that uses **native function calling** on top of the local **Qwen2.5-7B-Instruct** model (served by llama.cpp). It can run Linux commands, read configuration/log files, and write controlled changes, all through a conversation in Spanish.

## What does it do?

- Answers sysadmin questions in Spanish.
- Executes shell commands on the local machine (`run_command`).
- Reads configuration files and logs (`read_file`).
- Writes files to allowed paths, blocking system directories (`write_file`).
- Maintains conversational context and performs up to 5 reasoning turns of tool→LLM.
- Plans and executes multi-step tasks without intermediate human intervention.

## Architecture

```
┌─────────────┐     HTTP JSON     ┌──────────────────┐
│  chat.py    │ ────────────────▶ │   agent.py       │
│ (CLI loop)  │                   │  orchestrator    │
└─────────────┘                   │  function calls  │
                                  └────────┬─────────┘
                                           │ tools schema
                                           ▼
                                  ┌──────────────────┐
                                  │    tools.py      │
                                  │ run_command      │
                                  │ read_file        │
                                  │ write_file       │
                                  └──────────────────┘
                                           │
                                           ▼
                                  ┌──────────────────┐
                                  │  Qwen2.5-7B-Instruct via    │
                                  │ llama.cpp :8083  │
                                  └──────────────────┘
```

- `chat.py`: interactive loop.
- `agent.py`: manages messages, calls the LLM, executes tool calls, and returns responses.
- `tools.py`: tool definitions and handlers.

## Model

The definitive model is **Qwen2.5-7B-Instruct** served by llama.cpp.

During development we evaluated **Qwen2.5-Coder-3B**, but it was discarded because its function calling was inconsistent: it produced malformed tool calls, invented non-existent functions, and ignored the JSON schema. Since native function calling is the core mechanism of the agent, Qwen2.5-Coder-3B was not reliable enough for unattended, multi-step SRE tasks.

Qwen2.5-7B-Instruct was chosen because it consistently emits valid `tool_calls` payloads, respects the declared schema, and completes multi-step plans correctly, while keeping acceptable latency on modest hardware.

- Production service points to `:8083` and loads **Qwen2.5-7B-Instruct**.
- Qwen2.5-Coder-3B has been removed from the server and is no longer available.
- All documentation, tests, and examples assume Qwen2.5-7B-Instruct as the backing model.

### Model quantization

The deployed instance uses a single quantization that balances tool-calling quality, context budget, and speed on a modest VPS.

| Quantization | Speed (tok/s) | RAM/VRAM | Observed quality | Use case |
|--------------|---------------|----------|------------------|----------|
| Q4_K_M       | 57 prompt / 20 gen | 4.7 GB   | Reference        | Production server with enough memory |

The current deployed instance uses **Qwen2.5-7B-Instruct-Q4_K_M** at :8083 with an 8K context window and `MAX_HISTORY_TOKENS=6000`. Older Qwen3-family and smaller Qwen2.5-Coder-3B models have been removed from the server. To avoid silent context overflow, `agent.py` now counts tokens with the real `/v1/tokenize` endpoint before compressing or truncating history, rather than estimating with a fixed chars-per-token ratio.

## Readline history

The interactive CLI now supports standard terminal line editing through Python's `readline` module:

- **Up / Down arrows**: browse previous commands entered in the current session and across sessions.
- **Left / Right arrows**: move the cursor to edit the current line.
- **Persistent history**: commands are saved to `data/.chat_history` and reloaded on startup (up to 500 entries).
- This works in any standard terminal on Linux, macOS, and in Windows terminals using a readline-compatible shell.

Session context (files read/written and tool results) is still managed by the agent; the readline history only stores the user's input lines.

## Roadmap

Features implemented in v2.1 (all completed):

- ✅ Native function calling over llama.cpp server (`/v1/chat/completions`)
- ✅ Tool `run_command`: execute shell commands with timeout, capturing stdout/stderr/exit_code/elapsed
- ✅ Tool `read_file`: read files with permission checks and size limits
- ✅ Tool `write_file`: write files, blocking critical system paths
- ✅ Conversational loop with up to 5 tool→LLM turns and persistent per-session context
- ✅ Multi-step planning and execution without intermediate human intervention
- ✅ Basic security: warning before destructive commands and protection of `/etc`, `/boot`, `/sys`, `/proc`, `/dev`
- ✅ Interactive CLI in Spanish (`chat.py`) with commands `salir`/`exit`/`quit`
- ✅ Readline history and cursor navigation in the CLI
- ✅ Complete README.md with architecture, usage, and roadmap
- ✅ Executive documentation in PDF (`docs/ejecutivo.pdf`)

## Multi-step planning

For complex tasks the agent does not perform a single function call: it first **thinks**, decomposes, and then executes the steps sequentially.

### How it works

1. **Planning prompt**: the system prompt instructs the LLM to generate a numbered plan of steps and keep executing it with the instruction `EJECUTA without explaining`.
2. **`MAX_TURNS=5`**: the function-calling loop allows up to 5 turns, enough for several-step tasks without falling short.
3. **Sequential execution**: each tool call is performed, its result is injected into context, and the LLM decides the next step until the task finishes or the turn budget runs out.
4. **No intermediate human intervention**: the model executes directly; the user only receives the final summarized result.

### Example execution

**User**: `install WordPress with Docker and MariaDB`

```text
Step 1: Verify Docker is installed and running.
Step 2: Create Docker network and MariaDB container with environment variables.
Step 3: Start WordPress container linked to MariaDB.
Step 4: Show final container and exposed port status.
```

The agent executes each step via `run_command`, receives the output, and advances automatically. At the end it responds with a summary of what was done.

### Benefits

- Resolves composite tasks without fragmenting the user's query.
- Leverages the LLM's reasoning to order dependencies (`first MariaDB, then WordPress`).
- Keeps the loop under control: it can ask for confirmation if it detects a destructive or critical step.

## Requirements

- Python 3.10+
- `requests` (`pip install requests`)
- llama.cpp server running Qwen2.5-7B-Instruct at `http://localhost:8083/v1/chat/completions`

## Usage

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

Type `salir`, `exit`, or `quit` to finish.

## Security

- Before destructive commands the model warns and asks for confirmation.
- `write_file` blocks system paths (`/etc`, `/boot`, `/sys`, `/proc`, `/dev`).
- The agent does not persist conversational history across sessions (only readline input history is kept).

## Files

- `agent.py` — function-calling orchestrator.
- `tools.py` — shell, read, and write tools.
- `chat.py` — terminal chat interface with readline history.
- `README.md` — this document.
- `CHANGELOG.md` — change history.
- `docs/ejecutivo.pdf` — executive summary in PDF.

## Version history

### v2.1 — SRE Agent with native function calling on Qwen2.5-7B-Instruct

- Definitive model set to Qwen2.5-7B-Instruct; Qwen2.5-Coder-3B evaluated and discarded due to inconsistent function calling.
- Readline history and cursor navigation in the interactive CLI (`chat.py`).
- Session context persisted across restarts.
- README updated with final model choice and readline section.
- Executive PDF regenerated.

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
