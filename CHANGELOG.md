# Changelog

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
