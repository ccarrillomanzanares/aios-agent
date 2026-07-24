# Resumen Ejecutivo — aios-agent v2.3

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
| `scripts/launch_llama.py` | Lanzador de llama-server con configuración por defecto. |
| `scripts/firstboot.sh` | Configuración de primer arranque. |
| `systemd/aios-llama.service` | Servicio systemd del servidor de modelos. |
| `systemd/aios-agent.service` | Servicio systemd del agente interactivo. |

## Novedades de la v2.3

1. **Rutas estándar de sistema**
   - Servidor: `/usr/local/bin/llama-server`
   - Modelos: `/usr/local/share/aios/models/`
   - Código del agente: `/usr/local/bin/aios-agent/`
   - Configuración: `~/.aios/config.yaml`
   - Claves API: `~/.aios/.env`

2. **Instalador a disco duro (`scripts/aios-install`)**
   - Particiona GPT, formatea ext4 y copia el sistema live.
   - Instala GRUB, genera `/etc/fstab` por UUID.
   - Habilita `aios-llama.service`.
   - Genera `~/.aios/config.yaml` para el usuario `aios`.

3. **Configuración por defecto**
   - `launch_llama.py` crea `~/.aios/config.yaml` automáticamente si no existe, con modelo, threads y contexto adaptados al hardware.

4. **Wrapper `aios`**
   - Comando `/usr/local/bin/aios` inicia el chat interactivo sin recordar la ruta completa.

5. **Systemd refinado**
   - `aios-llama.service`: habilitado para inicio automático.
   - `aios-agent.service`: deshabilitado por defecto porque requiere terminal interactiva.

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

- Versión actual: **v2.3**
- Rama: `main`
- Última actualización: 24 de julio de 2026
- Repositorio: https://github.com/ccarrillomanzanares/aios-agent
