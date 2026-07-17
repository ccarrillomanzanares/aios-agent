# Seguridad de SRE-Copilot

## Principio general

**Primero, no romper nada.** El orquestador nunca debe modificar el sistema sin aprobación explícita del operador.

## Categorías de comandos

### 1. Solo lectura (auto-aprobados)

Comandos que solo consultan información, nunca modifican el sistema:

`ls`, `cat`, `df`, `free`, `ps`, `ss`, `netstat`, `ip`, `systemctl status`,
`journalctl`, `dmesg`, `lsof`, `top`, `htop`, `uptime`, `uname`, `hostname`,
`ping`, `dig`, `curl`, `wget`, `grep`, `find`, `lscpu`, `lsblk`, etc.

### 2. Requieren aprobación

Cualquier comando que:
- Escriba en disco (`>`, `>>`, `cat >`, `tee`).
- Use pipes (`|`) o secuencias (`;`, `&&`, `||`).
- Use subshells (`$()`, backticks).
- Use estructuras shell (`while`, `for`, `if`).
- Modifique permisos (`chmod`, `chown`).
- Inicie/procesos en background (`&`, `nohup`, `systemd-run`).

### 3. Bloqueados (nunca se ejecutan)

`rm`, `dd`, `mkfs`, `fdisk`, `parted`, `gparted`, `shutdown`, `reboot`,
`halt`, `poweroff`, `kill`, `pkill`, `killall`, `umount`, `mount`, `iptables`,
`nft`, `ufw`, `apt`, `apt-get`, `dpkg`, `yum`, `dnf`, `pacman`, `zypper`,
`snap`, `flatpak`, `useradd`, `userdel`, `usermod`, `groupadd`, `groupdel`,
`groupmod`, `passwd`.

## Logs

Toda ejecución, rechazo y error se guarda en:

```
/home/ccmai/sre-copilot/logs/orchestrator.log
```

## Responsabilidad

El operador humano tiene la última palabra. El orquestador es una herramienta
asistida, no un agente autónomo.

## Recomendaciones de uso

- No apruebes comandos que no entiendas.
- Usa `dry_run=True` en `executor.run_command()` para previsualizar.
- Revisa el contexto RAG antes de ejecutar comandos en entornos críticos.
- Mantén copias de seguridad de configuraciones antes de cambios mayores.
