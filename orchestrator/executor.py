#!/usr/bin/env python3
"""Executor seguro de comandos Linux para el orquestador SRE.

Mejoras clave:
- stdin cerrado para evitar que comandos interactivos esperen input.
- DEBIAN_FRONTEND=noninteractive para apt/dpkg.
- Auto -y en apt install/remove/upgrade si no se especificó.
- Monitor de actividad por inactividad en stdout/stderr (no timeout absoluto rígido).
- Lectura no-bloqueante para capturar barras de progreso de apt, docker, rsync, etc.
"""
import datetime
import fcntl
import os
import re
import select
import shlex
import subprocess
import time
from pathlib import Path


LOG_FILE = Path("/home/ccmai/sre-copilot/logs/orchestrator.log")

# Comandos de solo lectura permitidos sin aprobación explícita.
READONLY_COMMANDS = {
    "systemctl", "journalctl", "ps", "top", "htop", "free", "df", "du",
    "ls", "cat", "less", "more", "head", "tail", "grep", "find", "which",
    "whereis", "file", "stat", "lsof", "ss", "netstat", "ip", "route",
    "ping", "dig", "nslookup", "curl", "wget", "uname", "hostname", "uptime",
    "who", "w", "id", "groups", "lsblk", "blkid",
    "smartctl", "hdparm", "lscpu", "lspci", "lsusb", "lsmod", "modinfo",
    "dmesg", "vmstat", "iostat", "mpstat", "sar", "nproc", "pwd", "echo",
    "date", "timedatectl", "getent", "awk", "sed", "sort", "uniq", "wc",
    "tar", "zipinfo", "unzip", "md5sum", "sha256sum", "diff",
    "docker", "docker-compose", "podman", "kubectl",
    "nginx", "apache2ctl", "apachectl", "php-fpm",
    "git",
    "python3", "python", "pip",
}

# Argumentos destructivos que convierten un comando readonly en peligroso.
DANGEROUS_ARGS = {
    "-rf", "--remove", "--delete", "--kill", "stop", "restart",
    "disable", "enable", "reload", "reset", "poweroff", "reboot", "halt",
    "--purge", "remove", "autoremove", "install", "upgrade", "dist-upgrade",
}

# Comandos que nunca se ejecutarán automáticamente.
BLACKLIST_COMMANDS = {
    "rm", "dd", "mkfs", "fdisk", "parted", "gparted", "shutdown", "reboot",
    "halt", "poweroff", "init", "telinit", "kill", "pkill", "killall",
    "umount", "mount", "chown", "chmod", "chgrp", "userdel", "useradd",
    "usermod", "groupdel", "groupadd", "groupmod", "passwd", "iptables",
    "nft", "ufw", "apt", "apt-get", "dpkg", "yum", "dnf", "pacman", "zypper",
    "snap", "flatpak", "service",
}

# Metacaracteres que implican redirección, pipe, secuencia o subshell.
SHELL_METACHARS = set(";|&><$`\"'")
SHELL_KEYWORDS = ("while", "for ", "if ", "case ", "function", "until ",
                  " do ", " then ", " else ", " fi", " done")


def log(msg: str):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        ts = datetime.datetime.now().isoformat()
        f.write(f"[{ts}] {msg}\n")


def has_shell_metacharacters(cmd: str) -> bool:
    """Detecta si el comando contiene redirecciones, pipes, secuencias o subshells."""
    if any(c in cmd for c in SHELL_METACHARS):
        return True
    if any(kw in cmd.lower() for kw in SHELL_KEYWORDS):
        return True
    return False


def has_dangerous_args(args: list[str]) -> bool:
    lowered = [a.lower() for a in args[1:]]
    return any(a in DANGEROUS_ARGS for a in lowered)


def is_readonly_command(cmd: str, args: list[str]) -> bool:
    if not args:
        return False
    base = args[0]
    if base not in READONLY_COMMANDS:
        return False
    if has_dangerous_args(args):
        return False
    # Si contiene metacaracteres de shell, no es un simple comando readonly seguro
    if has_shell_metacharacters(cmd):
        return False
    return True


def is_blacklisted(args: list[str]) -> bool:
    if not args:
        return False
    base = args[0]
    return base in BLACKLIST_COMMANDS


def requires_shell(cmd: str, args: list[str]) -> bool:
    """Determina si el comando necesita ser ejecutado con bash -c."""
    if not args:
        return False
    if has_shell_metacharacters(cmd):
        return True
    if args[0] in READONLY_COMMANDS or args[0] in BLACKLIST_COMMANDS:
        return False
    return True


def _normalize_apt(cmd_list: list[str]) -> list[str]:
    """Asegura que apt install/remove/upgrade/dist-upgrade lleven -y."""
    if not cmd_list:
        return cmd_list
    base = cmd_list[0]
    if base not in ("apt", "apt-get"):
        return cmd_list
    lowered = [a.lower() for a in cmd_list]
    has_action = any(a in lowered for a in ("install", "remove", "purge", "upgrade", "dist-upgrade"))
    has_y = any(a in ("-y", "--yes", "-yes") for a in cmd_list)
    if has_action and not has_y:
        # Insertar -y justo después del comando base
        return [cmd_list[0], "-y"] + cmd_list[1:]
    return cmd_list


def _normalize_sudo(cmd_list: list[str]) -> list[str]:
    """Fuerza sudo no interactivo (-n) para evitar que pida contraseña sin TTY."""
    if not cmd_list or cmd_list[0] != "sudo":
        return cmd_list
    if len(cmd_list) > 1 and cmd_list[1] == "-n":
        return cmd_list
    return ["sudo", "-n"] + cmd_list[1:]


def validate_command(cmd: str) -> tuple[list[str], str]:
    """Valida un comando. Devuelve (args, error_message)."""
    cmd = cmd.strip()
    if not cmd:
        return [], "Comando vacío."
    try:
        args = shlex.split(cmd)
    except ValueError as e:
        return [], f"Error de sintaxis: {e}"
    if not args:
        return [], "Comando vacío."
    if is_blacklisted(args):
        return [], f"Comando bloqueado por seguridad: {args[0]}"
    return args, ""


DEFAULT_TIMEOUT = 180
MAX_INACTIVITY_TIMEOUT = 60
MAX_TOTAL_TIMEOUT = 600


def _make_non_blocking(stream):
    fd = stream.fileno()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def _run_with_activity_monitor(cmd_list, shell, inactivity_timeout, max_total_timeout):
    """Ejecuta un comando matándolo solo si no hay actividad en stdout/stderr."""
    start = time.time()

    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"

    process = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        env=env,
        text=True,
        shell=shell,
    )

    _make_non_blocking(process.stdout)
    _make_non_blocking(process.stderr)

    stdout_parts, stderr_parts = [], []
    last_activity = time.time()

    try:
        while True:
            elapsed = time.time() - start
            if elapsed >= max_total_timeout:
                raise subprocess.TimeoutExpired(cmd_list, max_total_timeout)

            if process.poll() is not None:
                # Leer cualquier resto no bloqueante
                for stream, parts in ((process.stdout, stdout_parts), (process.stderr, stderr_parts)):
                    try:
                        while True:
                            chunk = stream.read(4096)
                            if not chunk:
                                break
                            parts.append(chunk)
                            last_activity = time.time()
                    except (BlockingIOError, OSError):
                        pass
                break

            rlist, _, _ = select.select([process.stdout, process.stderr], [], [], 1.0)
            if not rlist:
                if time.time() - last_activity > inactivity_timeout:
                    raise subprocess.TimeoutExpired(cmd_list, inactivity_timeout)
                continue

            for stream in rlist:
                parts = stdout_parts if stream is process.stdout else stderr_parts
                try:
                    chunk = stream.read(4096)
                    if chunk:
                        parts.append(chunk)
                        last_activity = time.time()
                except (BlockingIOError, OSError):
                    pass

    except subprocess.TimeoutExpired as exc:
        log(f"TIMEOUT (inactividad {inactivity_timeout}s o total {max_total_timeout}s): {' '.join(cmd_list) if isinstance(cmd_list, list) else cmd_list}")
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=5)
        except Exception:
            pass
        return {
            "success": False,
            "stdout": "".join(stdout_parts),
            "stderr": "".join(stderr_parts) + f"\n[TIMEOUT] Proceso terminado tras inactividad > {inactivity_timeout}s o total > {max_total_timeout}s.",
            "returncode": None,
        }

    returncode = process.wait(timeout=10)
    return {
        "success": returncode == 0,
        "stdout": "".join(stdout_parts),
        "stderr": "".join(stderr_parts),
        "returncode": returncode,
    }


def run_command(cmd: str, dry_run: bool = False, auto_approve_readonly: bool = True,
                approved: bool = False,
                timeout: int = DEFAULT_TIMEOUT, inactivity_timeout: int = MAX_INACTIVITY_TIMEOUT,
                max_total_timeout: int = MAX_TOTAL_TIMEOUT) -> dict:
    args, error = validate_command(cmd)
    if error:
        return {"success": False, "stdout": "", "stderr": error, "returncode": None}

    # Normalizar apt y sudo para que no sean interactivos
    args = _normalize_apt(args)
    args = _normalize_sudo(args)
    cmd = " ".join(shlex.quote(a) for a in args)

    needs_approval = True
    if auto_approve_readonly and is_readonly_command(cmd, args):
        needs_approval = False

    if dry_run:
        return {"success": True, "stdout": f"[dry-run] {cmd}", "stderr": "", "returncode": 0,
                "needs_approval": needs_approval}

    if needs_approval and not approved:
        print(f"\n🛡️  Comando a ejecutar: {cmd}")
        print(f"   Timeout inactividad: {inactivity_timeout}s | Total: {max_total_timeout}s")
        answer = input("¿Ejecutar? [s/n/edit]: ").strip().lower()
        if answer == "edit":
            new_cmd = input("Escribe el comando corregido: ").strip()
            return run_command(new_cmd, dry_run=False, auto_approve_readonly=auto_approve_readonly,
                               approved=approved,
                               timeout=timeout, inactivity_timeout=inactivity_timeout,
                               max_total_timeout=max_total_timeout)
        if answer not in ("s", "sí", "si", "y", "yes"):
            log(f"RECHAZADO por usuario: {cmd}")
            return {"success": False, "stdout": "", "stderr": "Comando rechazado por el usuario.",
                    "returncode": None}

    log(f"EJECUTANDO: {cmd}")
    try:
        if requires_shell(cmd, args):
            log("USANDO SHELL bash -c")
            # Reconstruir la lista a partir del comando original para shell=True
            # Sin embargo, usamos el cmd normalizado ya como string
            result = _run_with_activity_monitor(
                [cmd],
                shell=True,
                inactivity_timeout=inactivity_timeout,
                max_total_timeout=max_total_timeout,
            )
        else:
            result = _run_with_activity_monitor(
                args,
                shell=False,
                inactivity_timeout=inactivity_timeout,
                max_total_timeout=max_total_timeout,
            )
        log(f"RESULTADO rc={result['returncode']} stdout_len={len(result['stdout'])} stderr_len={len(result['stderr'])}")
        return result
    except Exception as e:
        log(f"ERROR: {cmd} -> {e}")
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": None}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    args = parser.parse_args()
    print(run_command(args.command, auto_approve_readonly=False, approved=True))
