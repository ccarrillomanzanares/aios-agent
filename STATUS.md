# SRE Copilot - Estado del MVP

## Resumen

Sistema funcional en VPS `ccmai@31.220.80.78` bajo `/home/ccmai/sre-copilot/`.

## Componentes desplegados

1. **LLM local CPU:**
   - Backend: `llama.cpp` build 5200.
   - Modelo activo: `Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf` (~5.4 GB).
   - Servicio systemd user: `sre-llm.service` en `127.0.0.1:8080`.
   - API OpenAI-compatible en `http://127.0.0.1:8080/v1`.
   - Cliente con formato manual Llama-3 + detección Phi-4.

2. **RAG:**
   - Embeddings: `intfloat/multilingual-e5-large`.
   - Vector DB: ChromaDB en `/home/ccmai/sre-copilot/rag/chroma_db`.
   - Dataset: 96 documentos técnicos + manpages locales.
   - **507 chunks indexados.**
   - Re-ranker por keywords con bonus para metadatos del sistema.

3. **Orquestador:**
   - CLI interactivo con intenciones EXPLAIN/COMMAND/PLAN/ASK/DONE.
   - Historial de conversación (últimos 5 turnos).
   - Modo PLAN con aprobación paso a paso.
   - Executor seguro con whitelist de solo-lectura y blacklist destructiva.

4. **Evaluación:**
   - Suite `scripts/evaluate.py` con 7 casos.
   - **Resultado: 7/7 PASS.**

## Seguridad activa

- Comandos de solo lectura auto-aprobados.
- Redirecciones, pipes, secuencias y subshells requieren aprobación.
- Lista negra de comandos destructivos.
- Logs en `/home/ccmai/sre-copilot/logs/orchestrator.log`.

## Documentación

- `README.md`
- `SECURITY.md`
- `DECISIONS.md`
- `STATUS.md`

## Nuevos temas añadidos al dataset

- **Seguridad:** SSH hardening, sudoers/PAM, UFW, firewalld, auditd, AppArmor, SELinux, OpenSCAP/CIS, Lynis, WireGuard, OpenVPN, Tailscale, certbot/acme.sh.
- **Redes:** iproute2, VLAN/bonding/bridge, HAProxy, Traefik, Caddy, Squid, BIND9, Unbound, DHCP.
- **Almacenamiento:** LVM, ZFS, Btrfs, mdadm, LUKS, NFS, rsync, restic, BorgBackup.
- **Bases de datos:** PostgreSQL, MySQL/MariaDB, Redis.
- **Monitorización:** Prometheus Node Exporter + Alertmanager, Grafana, Loki/Promtail, ELK/EFK, Netdata.
- **Contenedores:** Docker Compose, Podman, Kubernetes básico, Helm, Kustomize.
- **Automatización:** Ansible, Terraform, cloud-init, GitHub Actions, GitLab CI, systemd timers.
- **Troubleshooting:** strace/ltrace, perf/flame graphs, Sysdig/Falco, cgroup v2, tuned/cpupower, I/O schedulers, zram/zswap.
- **Cloud:** AWS CLI, rclone/s3cmd.
- **Servicios clásicos:** Postfix, OpenLDAP cliente, Samba, SFTP chroot.

## Pruebas realizadas

- RAG: 507 chunks, retrieval correcto con re-ranker.
- LLM: responde en español, identifica el modelo, genera comandos correctos.
- Orquestador: historial, modo plan, seguridad, evaluador 7/7.
- Executor: solo-lectura auto, scripts con heredoc aprobados, destructivos bloqueados.

## Notas de operación

- `TMPDIR` apuntado a `/home/ccmai/sre-copilot/tmp`.
- Backups de modelos: Llama-3.2-3B y Phi-4-mini 3.8B.
- No se tocó `/lfs-rw` ni archivos del proyecto LFS.
- Procesos `llama-server` huérfanos eliminados previamente.

## Pendientes futuros (opcionales)

- Afinar re-ranker para temas más específicos.
- Añadir manpages locales de más herramientas nuevas (rsync, lvm, zfs, etc.).
- Implementar tests de seguridad más exhaustivos.
- Probar otros modelos pequeños si fuese necesario.
