# Security practices applicable to aios-agent (OWASP-based)

## Implemented
- **Tool allowlist**: dangerous commands blocked before execution (rm -rf /, dd, mkfs, fdisk, chmod -R)
- **Human-in-the-loop**: LLM prompts user before destructive actions
- **Memory isolation**: procedural cache only stores static knowledge, not dynamic command output
- **Logging**: all tool calls logged to audit.jsonl (timestamp, query, tool, result)
- **Cost controls**: MAX_TURNS=10, MAX_TOKENS=512, timeout per tool call

## Does NOT apply (single-user, local model, no external APIs)
- Multi-agent security (only one agent)
- MCP trust / supply chain (all tools are our own, no third-party skills)
- Encryption at rest (local VPS, single user)
- User isolation (only ccmai)
- Data exfiltration via API (no external calls except self-hosted Firecrawl)
- Denial of Wallet (local model, no token cost)
- Cross-session boundaries (same user, same session)
- OAuth / external tool authorization

## Pending (if agent is exposed via web/Telegram)
- Container sandbox: run agent as non-sudo user or in Docker
- Input sanitization: validate user input before LLM processing
- Rate limiting: prevent abuse if exposed publicly

## References
- OWASP AI Agent Security Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html
- NVIDIA Practical Security Guidance for Sandboxing Agentic Workflows
