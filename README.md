# AIOS Agent

Agente SRE semiautónomo con function calling, diseñado para ejecutarse en local (CPU) o cloud.

## Arquitectura

```
┌──────────────────────────────────────────────────┐
│                    chat.py                        │
│  (CLI interactivo con readline + history)         │
├──────────────────────────────────────────────────┤
│                    agent.py                       │
│  (bucle de function calling: llama.cpp API +      │
│   tools + memoria procedural + compresión)        │
├──────────────────────────────────────────────────┤
│  tools.py     memory.py    process.py  playbook.py│
│  (11 tools)   (caché)      (PTY)       (YAML)    │
└──────────────────────────────────────────────────┘
```

## Instalación

### Local (CPU, recomendado)

```bash
git clone https://github.com/ccarrillomanzanares/aios-agent
cd aios-agent
pip install -r requirements.txt

# Descargar modelo
python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download(bartowski/Qwen_Qwen3-8B-GGUF, Qwen_Qwen3-8B-Q4_K_M.gguf, local_dir=models/)"

# Iniciar servidor llama.cpp
/path/to/llama-server -m models/Qwen_Qwen3-8B-Q4_K_M.gguf --host 127.0.0.1 --port 8083 -c 32768 -t 14 --jinja

# Ejecutar agente
python3 chat.py
```

### ISO AIOS LFS

El agente está preinstalado en la ISO AIOS LFS live. Ver [aios-lfs](https://github.com/ccarrillomanzanares/aios-lfs) para la ISO que incluye este agente.

### Instalación a disco desde la ISO AIOS LFS

La ISO live incluye el instalador `aios-install` para escribir el sistema en disco duro. `setup.py` expone la opción **4: INSTALL TO DISK**:

1. Iniciar la ISO AIOS LFS y abrir una terminal.
2. Ejecutar `setup.py` y elegir la opción **`4) INSTALL TO DISK`**.
3. El setup lanza el instalador `aios-install`.
4. Al terminar la instalación, el setup pregunta si se desea reiniciar (`reboot`).

**Flujo de setup.py:**

```text
1) Configure AIOS
2) Start AIOS (local)
3) Exit
4) INSTALL TO DISK   <-- nueva opción
```

- Seleccionar `4` ejecuta `/usr/local/bin/aios-install`.
- Tras completar la instalación, setup solicita confirmación para reiniciar el sistema.

## Boot flow en la ISO AIOS LFS

El arranque gráfico del agente sigue este flujo secuencial:

1. **login** — autenticación del usuario de la sesión.
2. **aios-session** — script de arranque de sesión (`scripts/aios-session`) que:
   - lanza el setup inicial si no existe `~/.aios/config.yaml`;
   - una vez configurado, inicia el entorno gráfico con `startx`;
   - `i3` arranca como gestor de ventanas;
   - `i3` lanza un `xterm` que ejecuta el agente (`aios` / `chat.py`).

El servicio de modelo (`aios-llama.service`) no arranca por defecto en boot; se activa durante el setup cuando se elige modo `local` o `hybrid`.

## Configuración

Primer arranque: `scripts/aios-session` ejecuta el wizard de setup automáticamente si falta `~/.aios/config.yaml`.

Fichero de configuración: `~/.aios/config.yaml`

```yaml
mode: local
local:
  model: Qwen_Qwen3-8B-Q4_K_M.gguf
  model_name: Qwen3-8B-Instruct
  threads: 14
  context: 32768
cloud:
  provider: null
  model: null
```

### Modos

- **local**: usa modelo local via llama.cpp en :8083
- **cloud**: usa API externa (DeepSeek, OpenAI, Anthropic, etc.)
- **hybrid**: local para simple, cloud para complejo

## Herramientas (function calling)

| Tool | Descripción |
|---|---|
| `run_command` | Ejecuta comandos shell (con bloqueo de peligrosos + confirmación) |
| `read_file` | Lee archivos |
| `write_file` | Escribe archivos |
| `git_operation` | Operaciones git |
| `mcp_call` | Llamadas a servidores MCP |
| `run_playbook` | Ejecuta playbooks YAML |
| `process_start` | Inicia proceso interactivo (PTY) |
| `process_send` | Envía entrada a proceso interactivo |
| `process_close` | Cierra proceso interactivo |
| `process_list` | Lista procesos activos |
| `web_search` | Búsqueda web via Firecrawl |

## Scripts auxiliares

| Script | Descripción |
|---|---|
| `scripts/aios-session` | Arranque de sesión gráfica en la ISO: detecta si existe `~/.aios/config.yaml`, ejecuta setup en caso contrario, luego lanza `startx` → `i3` → `xterm` con el agente |
| `scripts/launch_llama.py` | Lanza llama-server si existe config y `mode` es `local`/`hybrid`. No crea config por defecto; sale limpio si falta o `mode=cloud` |
| `scripts/firstboot.sh` | Wizard de primer arranque (setup + enable servicios) |
| `scripts/aios-install` | Instala ISO AIOS LFS a disco duro |
| `setup.py` | Wizard de instalación y arranque en la ISO. Opciones: `1) Configure AIOS`, `2) Start AIOS (local)`, `3) Exit`, `4) INSTALL TO DISK` |

### setup.py — Opción 4: INSTALL TO DISK

`setup.py` coordina la configuración inicial y el lanzamiento del agente desde la ISO AIOS LFS. Su menú incluye ahora la opción **`4) INSTALL TO DISK`**:

- Al elegir `4`, `setup.py` ejecuta el instalador `aios-install`.
- Una vez que `aios-install` finaliza, `setup.py` pregunta al usuario si desea reiniciar el equipo.
- El reinicio permite arrancar desde el disco recién instalado.

Ejemplo de interacción:

```text
$ sudo setup.py
Seleccione una opción:
  1) Configure AIOS
  2) Start AIOS (local)
  3) Exit
  4) INSTALL TO DISK
Opción: 4
[aios-install] Instalando AIOS LFS al disco...
[aios-install] Instalación completada.
¿Desea reiniciar ahora? [s/N]:
```

> **Nota:** La opción 4 requiere privilegios de root para escribir en el disco de destino. Se recomienda ejecutar `setup.py` con `sudo` cuando se vaya a usar.

## Systemd (integración ISO)

```
/usr/lib/systemd/system/
├── aios-llama.service    # llama-server (disabled at boot, se activa en setup si local/híbrido)
└── aios-agent.service    # chat.py interactivo (disabled, lo lanza i3)
```

- `aios-llama.service` se desactiva en la ISO (`systemctl disable aios-llama.service`) y solo se habilita/arranca cuando setup.py elige `local` o `hybrid`.
- `sshd` está deshabilitado en la ISO, sin host keys fijas; si se necesita, se arranca manualmente (`/etc/rc.d/init.d/sshd start`) y se regeneran las keys al primer uso.
- Firefox se ha eliminado del autostart gráfico; no se abre automáticamente al iniciar sesión.

## Rutas en ISO

| Componente | Ruta |
|---|---|
| Repo agente | `/usr/local/bin/aios-agent/` |
| llama-server | `/usr/local/bin/llama-server` |
| Librerías | `/usr/local/lib/llama/` |
| Modelo | `/usr/local/share/aios/models/` |
| Instalador | `/usr/local/bin/aios-install` |
| Wrapper | `/usr/local/bin/aios` |

## Referencia cruzada a la ISO

Para construir o personalizar la imagen live que contiene este agente, consulta el repositorio [aios-lfs](https://github.com/ccarrillomanzanares/aios-lfs).

## Dependencias

- Python 3.11+
- `requests`, `pyyaml`
- llama.cpp compilado (`llama-server`)
- Modelo GGUF (Qwen3-8B, Qwen2.5-7B, etc.)

## Licencia

MIT
