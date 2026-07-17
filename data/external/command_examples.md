# Ejemplos de comandos seguros para SRE-Copilot

## Crear un script bash correctamente

Ejemplo de comando COMMAND para crear un script que imprime un mensaje cada segundo durante 5 segundos:

```bash
cat > /tmp/mi_script.sh << 'EOF'
#!/bin/bash
set -euo pipefail
timeout 5s bash -c 'while true; do echo "Hola"; sleep 1; done'
EOF
chmod +x /tmp/mi_script.sh
```

Nota: el contenido del script va DENTRO del heredoc. No redirijas la salida de `timeout` al archivo; el propio heredoc define el archivo.

## Listar archivos

```bash
ls -la
```

## Ver estado de un servicio

```bash
systemctl status nginx
```

## Ver espacio en disco

```bash
df -h
```

## Ver logs recientes

```bash
journalctl -n 20 --no-pager
```

## Revisar procesos

```bash
ps aux
```

## No hacer nunca sin aprobación explícita

- Instalar o eliminar paquetes (`apt`, `yum`, `dnf`, `pacman`).
- Formatear discos (`mkfs`, `dd`).
- Borrar archivos (`rm -rf`).
- Reiniciar o apagar (`reboot`, `shutdown`).
- Modificar reglas de firewall (`iptables`, `nftables`, `ufw`).
