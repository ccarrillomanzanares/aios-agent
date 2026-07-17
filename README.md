# SRE Copilot

Asistente de administración de sistemas Linux basado en LLM local + RAG + orquestador seguro.

## Arquitectura

```
Usuario
  │
  ▼
CLI interactivo (orchestrator/main.py)
  │
  ├──► RAG (ChromaDB + intfloat/multilingual-e5-large)
  │
  └──► LLM local (llama.cpp + Meta-Llama-3.1-8B-Instruct)
            │
            ▼
        Executor seguro (solo-lectura auto, resto con aprobación)
```

## Ubicación

`/home/ccmai/sre-copilot/` en el VPS `31.220.80.78`.

## Inicio rápido

```bash
ssh ccmai@31.220.80.78
cd /home/ccmai/sre-copilot
source venv/bin/activate

# Orquestador interactivo
python orchestrator/main.py

# Evaluación automática
python scripts/evaluate.py

# Reconstruir índice RAG
python rag/build_index.py --reset
# O con progreso detallado
python scripts/build_index_verbose.py
```

El servicio LLM ya está activo como `sre-llm.service`:

```bash
systemctl --user status sre-llm.service
```

## Modos del orquestador

- **EXPLAIN:** respuesta informativa.
- **COMMAND:** un solo comando, aprobación si no es solo-lectura.
- **PLAN:** lista de comandos; se pide aprobación paso a paso.
- **ASK:** aclaración al usuario.
- **DONE:** tarea finalizada.

## Seguridad

- Lista blanca de comandos de solo lectura (`ls`, `df`, `systemctl status`, `journalctl`, etc.).
- Cualquier redirección (`>`, `>>`), pipe (`|`), secuencia (`;`, `&&`, `||`) o subshell requiere aprobación.
- Lista negra de comandos destructivos.
- Logs en `/home/ccmai/sre-copilot/logs/orchestrator.log`.

## Modelo

- **Base:** `Meta-Llama-3.1-8B-Instruct-GGUF`
- **Quant:** `Q5_K_M` (~5.4 GB)
- **Backend:** `llama.cpp` build 5200
- **API:** OpenAI-compatible en `http://127.0.0.1:8080/v1`
- **Contexto:** 8192 tokens

Cambiar de modelo:

```bash
MODEL=/home/ccmai/sre-copilot/models/Otro.gguf systemctl --user restart sre-llm.service
```

Modelos disponibles:

- `Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf` (activo)
- `Llama-3.2-3B-Instruct-Q4_K_M.gguf` (backup)
- `microsoft_Phi-4-mini-instruct-Q4_K_M.gguf` (backup, no probado con éxito)

## Dataset

96 documentos técnicos indexados en ChromaDB (507 chunks):

### Seguridad
- SSH hardening, sudoers/PAM
- UFW, firewalld, nftables
- auditd, AppArmor, SELinux
- OpenSCAP/CIS, Lynis
- WireGuard, OpenVPN, Tailscale
- Fail2Ban, certbot/acme.sh

### Redes
- iproute2, VLAN/bonding/bridge
- HAProxy, Traefik, Caddy, Squid
- BIND9, Unbound, DHCP

### Almacenamiento y backups
- LVM, ZFS, Btrfs, mdadm, LUKS
- NFS, rsync, restic, BorgBackup

### Bases de datos y mensajería
- PostgreSQL, MySQL/MariaDB, Redis

### Monitorización y logs
- Prometheus + Node Exporter + Alertmanager
- Grafana, Loki/Promtail, ELK/EFK, Netdata

### Contenedores y virtualización
- Docker, Docker Compose, Podman
- Kubernetes básico, Helm, Kustomize

### Automatización e infraestructura
- Ansible, Terraform, cloud-init
- GitHub Actions, GitLab CI
- systemd timers

### Rendimiento y troubleshooting
- strace/ltrace, perf/flame graphs
- Sysdig/Falco, cgroup v2
- tuned/cpupower, I/O schedulers
- zram/zswap

### Cloud
- AWS CLI, rclone/s3cmd

### Servicios clásicos
- Postfix, OpenLDAP cliente, Samba
- SFTP chroot

### Sistema y referencia
- systemd, systemd-networkd, systemd timers
- Linux kernel sysctl, proc filesystem
- Manpages locales de herramientas clave
- SRE-Copilot metadata

## Scripts útiles

- `scripts/start_llm.sh` — arranca `llama-server`.
- `scripts/fetch_sre_docs.py` — descarga documentación pública.
- `scripts/extract_manpages.sh` — extrae manpages del VPS.
- `scripts/gen_sre_docs.py` — genera guías SRE estándar.
- `rag/build_index.py` — reconstruye la base vectorial.
- `scripts/build_index_verbose.py` — reconstruye con progreso detallado.
- `scripts/debug_llm.py` — depura respuestas del LLM.
- `scripts/evaluate.py` — suite de evaluación automática.

## Configuración

- `rag/config.yaml`
- `orchestrator/prompts.yaml`

## Autor

Proyecto experimental de Carlos (SRE Copilot).
