# Changelog
## v2.1 — SRE Agent con function calling nativo sobre Qwen2.5-7B-Instruct

- Modelo definitivo fijado en Qwen2.5-7B-Instruct; descartados Qwen2.5-Coder-3B y otros modelos <7B por function calling poco fiable.
- 13 tools: `run_command`, `read_file`, `write_file`, `web_search`, `git_operation`, `mcp_call`, `run_playbook`, `process_start`, `process_send`, `process_close`, `process_list`, `cloud_reasoning`, `get_context_usage`.
- Memoria procedural Skill-Pro, compresión de contexto con conteo real de tokens vía `/v1/tokenize`, sesión persistente y recuperación de errores apt.
- Historial readline, navegación con cursores y Ctrl+C que interrumpe el turno actual sin salir del chat.
- Setup wizard (`setup.py`) con modos local/cloud/híbrido y 7 proveedores (DeepSeek V4 Flash/Pro, OpenAI, Anthropic, Google, Kimi, Ollama Cloud, OpenRouter); sesiones y memoria separadas por modo; `context_limit` por proveedor en `data/config.yaml`.
- Detección automática de RAM desde `/proc/meminfo` y escalado automático del contexto local: ≤8 GB → 8K, 12–16 GB → 32K, >16 GB → 64K.
- Asignación automática de threads CPU al 87.5% de los cores (p. ej. 14/16); el menú muestra `N/16 cores` en lugar de porcentaje.
- `cloud_reasoning` delega razonamiento complejo al cloud con el contexto local completo; `get_context_usage` muestra tokens usados vs. máximo.
- Compresión por modo: 95% del contexto local (32K por defecto) para local/híbrido, 50% del `context_limit` para cloud.
- Anti-bucle: si la misma tool + argumentos se repite ≥3 veces, se pregunta al usuario si abortar con timeout de 10 s.
- Correcciones: Docker `--format` ya no se marca como destructivo; endpoint local/híbrido corregido a `/v1/chat/completions`; API key oculta con `getpass`; se muestra N/16 cores; DeepSeek actualizado a V4 Flash y V4 Pro; añadido Ollama Cloud como proveedor; `.gitignore` actualizado con `gcc*`; disclaimer de responsabilidad en README; RAM mínima local subida de 8 GB a 12 GB.
- README.md y PDF ejecutivo actualizados.

## v2.0 — Agente SRE con function calling nativo sobre Qwen3-8B

- Reescritura completa del repositorio.
- Agente ligero de SRE con function calling nativo vía llama.cpp server.
- Nuevas herramientas:
  - `run_command`: ejecuta comandos shell en Linux.
  - `read_file`: lee archivos de configuración y logs.
  - `write_file`: escribe archivos, bloqueando rutas de sistema críticas.
- Soporte conversacional en español con hasta 5 turnos de razonamiento.
- Seguridad básica: advertencia antes de comandos destructivos y bloqueo de `/etc`, `/boot`, `/sys`, `/proc`, `/dev`.
- CLI interactivo en `chat.py`.
- README.md y PDF ejecutivo en `docs/ejecutivo.pdf`.
