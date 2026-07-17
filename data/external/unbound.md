# Unbound - Resolver DNS

## Instalación
```bash
sudo apt install unbound
```

## Configuración
```yaml
server:
    interface: 0.0.0.0
    access-control: 192.168.0.0/16 allow
    access-control: 127.0.0.0/8 allow
```

## Test
```bash
sudo systemctl restart unbound
dig @127.0.0.1 ejemplo.com
```
