# Resumen Ejecutivo — aios-agent v2.4

## Propósito

`aios-agent` es un asistente SRE (Site Reliability Engineering) ligero que utiliza **function calling nativo** sobre un modelo local Qwen servido por llama.cpp. Opera 100% offline en modo local, con opción a modelos cloud en modo cloud/híbrido. Ejecuta comandos Linux, lee y escribe archivos, gestiona procesos interactivos, consulta la web y aprende de la experiencia mediante memoria procedural.

## Componentes principales

| Archivo | Función |
|---------|---------|
| `agent.py` | Orquestador de function calling, compresión de contexto y sesiones persistentes. |
| `tools.py` | Definición y handlers de herramientas (shell, lectura, escritura, web, git, MCP, procesos). |
| `chat.py` | Bucle interactivo, carga de config y selección de modo. |
| `memory.py` | Memoria procedural persistente por modo (ProcMEM). |
| `process.py` | Gestión de procesos interactivos vía PTY. |
| `setup.py` | Asistente de configuración inicial (local/cloud/híbrido). |
| `scripts/aios-install` | Instalador de la ISO AIOS LFS a disco duro. |
| `scripts/launch_llama.py` | Lanzador de llama-server; no crea config, arranca solo en local/híbrido. |
| `scripts/firstboot.sh` | Configuración de primer arranque. |
| `systemd/aios-llama.service` | Servicio systemd del servidor de modelos (deshabilitado en boot). |
| `systemd/aios-agent.service` | Servicio systemd del agente interactivo (deshabilitado). |

## Novedades de la v2.4

1. **Rutas estándar de sistema**
   - Servidor: `/usr/local/bin/llama-server`
   - Modelos: `/usr/local/share/aios/models/`
   - Código del agente: `/usr/local/bin/aios-agent/`
   - Configuración: `~/.aios/config.yaml`
   - Claves API: `~/.aios/.env`

2. **Instalador a disco duro (`scripts/aios-install`)**
   - Particiona GPT, formatea ext4 y copia el sistema live.
   - Instala GRUB, genera `/etc/fstab` por UUID.
   - Genera `~/.aios/config.yaml` para el usuario `aios`.

3. **Systemd refinado (lazy start)**
   - `aios-llama.service`: deshabilitado en boot; `setup.py` lo habilita y arranca solo si el modo elegido es `local` o `hybrid`.
   - `aios-agent.service`: deshabilitado por defecto porque requiere terminal interactiva.
   - `sshd`: deshabilitado en la ISO, sin host keys fijas; se arranca manualmente si se requiere acceso remoto.

4. **launch_llama.py pasivo**
   - No crea `~/.aios/config.yaml` por defecto.
   - Sale limpio con código 0 si no existe config o si el modo es `cloud`.
   - Arranca el servidor solo cuando `mode` es `local` o `hybrid`.

5. **Referencia a AIOS LFS**
   - Este agente se incluye en la ISO `aios-lfs`: https://github.com/ccarrillomanzanares/aios-lfs.

## Seguridad

- Bloqueo de comandos peligrosos (`rm -rf /`, `dd`, `mkfs`, `fdisk`).
- Confirmación interactiva para comandos destructivos.
- Bloqueo de escritura en rutas de sistema críticas.
- Restricciones en operaciones git (no `reset`, `rebase`, `merge`, `stash`, ni borrado de ramas).

## Requisitos y despliegue

- Python 3.10+, `requests`, `pyyaml`.
- llama.cpp server en `127.0.0.1:8083` para modo local/híbrido.
- Para instalar a disco: ejecutar `aios-install` desde el entorno live de AIOS LFS.

## Estado del proyecto

- Versión actual: **v2.4**
- Rama: `main`
- Última actualización: 24 de julio de 2026
- Repositorio: https://github.com/ccarrillomanzanares/aios-agent
