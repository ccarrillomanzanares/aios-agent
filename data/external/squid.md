# Squid - Proxy HTTP

## Instalación
```bash
sudo apt install squid
```

## Configuración /etc/squid/squid.conf
```
http_port 3128
acl localnet src 192.168.0.0/16
http_access allow localnet
http_access deny all
```

## Recargar
```bash
sudo systemctl restart squid
```
