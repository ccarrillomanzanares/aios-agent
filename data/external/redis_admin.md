# Redis básico

## Instalación
```bash
sudo apt install redis-server
sudo systemctl enable --now redis-server
```

## CLI
```bash
redis-cli INFO
redis-cli MONITOR
redis-cli SLOWLOG GET 10
```

## Persistencia
```
appendonly yes
appendfsync everysec
```

## Seguridad
```
bind 127.0.0.1
requirepass contraseña
protected-mode yes
```
