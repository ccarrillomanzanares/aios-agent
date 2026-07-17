# Caddy - HTTPS automático

## Instalación
```bash
sudo apt install caddy
```

## Caddyfile
```
ejemplo.com {
    reverse_proxy localhost:8080
}
```

## Recargar
```bash
sudo caddy reload --config /etc/caddy/Caddyfile
```
