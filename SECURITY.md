# Security practices applicable to aios-agent (OWASP-based)

## Implemented
- **Tool allowlist**: dangerous commands blocked in tools.py (rm -rf /, rm -rf /*, dd to /dev/, mkfs, fdisk, chmod 000) ✅
- **Human-in-the-loop**: destructive commands (rm, sudo rm, format, dd) require y/N confirmation ✅
- **Input validation**: sanitize user input, limit 1000 chars, detect system prompt injection ✅
- **Memory isolation**: procedural cache only stores static knowledge, not dynamic command output ✅
- **Logging**: all tool calls logged to audit.jsonl (timestamp, query, tool, result) ✅
- **Cost controls**: MAX_TURNS=10, MAX_TOKENS=512, timeout per tool call ✅

## Pending (medium effort)
- **Sandbox execution**: run agent as non-sudo user or in Docker container ⏳ Medium

## Does NOT apply (single-user, local model, no external APIs)
- Multi-agent security
- MCP trust / supply chain
- Encryption at rest
- User isolation
- Data exfiltration via API
- Denial of Wallet (local model)
- Cross-session boundaries
- OAuth / external tool authorization

## References
- OWASP AI Agent Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- NVIDIA Practical Security Guidance for Sandboxing Agentic Workflows
