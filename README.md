# aios-agent v2.0 — Agente SRE con function calling nativo

Agente ligero de Operaciones de Fiabilidad de Sitio (SRE) que usa **function calling nativo** sobre el modelo local **Qwen3-8B** (servido por llama.cpp). Puede ejecutar comandos Linux, leer archivos de configuración/logs y escribir cambios controlados, todo a través de una conversación en español.

## ¿Qué hace?

- Responde preguntas de sysadmin en español.
- Ejecuta comandos shell en la máquina local (`run_command`).
- Lee archivos de configuración y logs (`read_file`).
- Escribe archivos en rutas permitidas, bloqueando directorios de sistema (`write_file`).
- Mantiene contexto conversacional y realiza hasta 5 turnos de razonamiento tool→LLM.

## Arquitectura

```
┌─────────────┐     HTTP JSON     ┌──────────────────┐
│  chat.py    │ ────────────────▶ │   agent.py       │
│ (CLI loop)  │                   │  orquestador     │
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
                                  │  Qwen3-8B vía    │
                                  │ llama.cpp :8083  │
                                  └──────────────────┘
```

- `chat.py`: bucle interactivo.
- `agent.py`: gestiona mensajes, llama al LLM, ejecuta tool calls y devuelve respuestas.
- `tools.py`: definición de herramientas y handlers.

## Requisitos

- Python 3.10+
- `requests` (`pip install requests`)
- llama.cpp server corriendo Qwen3-8B en `http://localhost:8083/v1/chat/completions`

## Uso

```bash
python3 chat.py
```

Ejemplos de consulta:

```text
> muestra el uso de disco
> lee /var/log/syslog
> escribe un script de backup en /tmp/backup.sh
> reinicia nginx
```

Escribe `salir`, `exit` o `quit` para terminar.

## Seguridad

- Antes de comandos destructivos el modelo advierte y pide confirmación.
- `write_file` bloquea rutas de sistema (`/etc`, `/boot`, `/sys`, `/proc`, `/dev`).
- El agente no guarda historial entre sesiones.

## Archivos

- `agent.py` — orquestador de function calling.
- `tools.py` — herramientas shell, lectura y escritura.
- `chat.py` — interfaz de chat por terminal.
- `README.md` — este documento.
- `CHANGELOG.md` — histórico de cambios.
- `docs/ejecutivo.pdf` — resumen ejecutivo en PDF.

## Licencia

MIT / Uso interno.
