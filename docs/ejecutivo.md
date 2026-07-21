# aios-agent v2.1 — Resumen Ejecutivo

## Propósito

aios-agent es un agente ligero de SRE que utiliza **function calling nativo** sobre el modelo local **Qwen3-8B** (served by llama.cpp). Responde en español, ejecuta comandos Linux, lee archivos de configuración y logs, y escribe archivos bajo ciertas rutas permitidas.

## Modelo definitivo

- **Qwen3-8B Q4_K_M** en `http://localhost:8083/v1/chat/completions`.
- Se evaluó **Qwen3-4B** y se descartó: su function calling era inconsistente (tool calls mal formados, funciones inventadas, ignoraba el esquema JSON).
- Qwen3-8B emite `tool_calls` válidos de forma consistente y completa planes multi-paso.

## Funcionalidades v2.1

| Funcionalidad | Estado |
|---------------|--------|
| Function calling nativo vía llama.cpp | [OK] |
| `run_command` con timeout y captura de salida | [OK] |
| `read_file` con comprobaciones de permisos y tamaño | [OK] |
| `write_file` bloqueando rutas críticas del sistema | [OK] |
| Bucle conversacional con hasta 5 turnos tool→LLM | [OK] |
| Planificación y ejecución multi-paso sin intervención | [OK] |
| Seguridad básica: advertencia antes de comandos destructivos | [OK] |
| CLI interactiva en español | [OK] |
| Historial readline (flechas arriba/abajo, cursor) | [OK] |
| Memoria de sesión persistente | [OK] |
| README.md y PDF ejecutivo actualizados | [OK] |

## Arquitectura

```
chat.py  --▶  agent.py  --▶  tools.py  --▶  Qwen3-8B vía llama.cpp:8083
```

- `chat.py`: bucle interactivo con readline.
- `agent.py`: orquestador de function calling y memoria procedural.
- `tools.py`: definición y manejadores de herramientas.

## Historial readline

La CLI ahora usa el módulo `readline` de Python:

- Flechas arriba/abajo para recorrer comandos anteriores.
- Flechas izquierda/derecha para mover el cursor.
- Historial persistente en `data/.chat_history` (hasta 500 entradas).

## Uso

```bash
python3 chat.py
```

Ejemplos:

```text
> muestra el uso de disco
> lee /var/log/syslog
> escribe un script de backup en /tmp/backup.sh
> reinicia nginx
```

Escribe `salir`, `exit` o `quit` para terminar.

## Seguridad

- Advertencia antes de comandos destructivos.
- `write_file` bloquea `/etc`, `/boot`, `/sys`, `/proc`, `/dev`.
- La memoria conversacional se guarda en sesión; el historial readline solo guarda líneas de entrada del usuario.

## Siguientes pasos recomendados

- Evaluar en escenarios reales de SRE (reinicio de servicios, diagnóstico de logs, backups).
- Añadir confirmación explícita del usuario para comandos destructivos.
- Integrar más herramientas: `git_operation`, gestión de paquetes, consulta de estado de systemd.

---
*Documento generado el 21 de julio de 2026.*
