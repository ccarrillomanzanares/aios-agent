# Fail2Ban para SSH — Guía SRE

## Configuración básica (sin instalar paquetes)

Si Fail2Ban ya está instalado, crea o edita la configuración del jail para SSH:

```bash
cat > /etc/fail2ban/jail.d/sshd.conf << 'EOF'
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
bantime = 3600
EOF
fail2ban-client reload
fail2ban-client status sshd
```

## Comandos útiles

- Ver estado general: `fail2ban-client status`
- Ver estado de un jail: `fail2ban-client status sshd`
- Banear una IP: `fail2ban-client set sshd banip 192.0.2.1`
- Desbanear una IP: `fail2ban-client set sshd unbanip 192.0.2.1`

## Reglas por defecto

El filtro `sshd` detecta intentos fallidos de autenticación en `/var/log/auth.log`.

## Verificación

```bash
journalctl -u fail2ban -n 20 --no-pager
```
