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

El agente está preinstalado en la ISO AIOS LFS live. Ver [aios-lfs-docs](https://github.com/ccarrillomanzanares/aios-lfs).

## Configuración

Primer arranque: `chat.py` ejecuta el wizard de setup automáticamente.

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
| `scripts/launch_llama.py` | Lanza llama-server con parámetros del config (crea config por defecto si no existe) |
| `scripts/firstboot.sh` | Wizard de primer arranque (setup + enable servicios) |
| `scripts/aios-install` | Instala ISO AIOS LFS a disco duro |

## Systemd (integración ISO)

```
/usr/lib/systemd/system/
├── aios-llama.service    # llama-server (enabled)
└── aios-agent.service    # chat.py interactivo (disabled, lo lanza i3)
```

## Rutas en ISO

| Componente | Ruta |
|---|---|
| Repo agente | `/usr/local/bin/aios-agent/` |
| llama-server | `/usr/local/bin/llama-server` |
| Librerías | `/usr/local/lib/llama/` |
| Modelo | `/usr/local/share/aios/models/` |
| Instalador | `/usr/local/bin/aios-install` |
| Wrapper | `/usr/local/bin/aios` |

## Dependencias

- Python 3.11+
- `requests`, `pyyaml`
- llama.cpp compilado (`llama-server`)
- Modelo GGUF (Qwen3-8B, Qwen2.5-7B, etc.)

## Licencia

MIT
