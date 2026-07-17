# Tailscale - VPN mesh

Tailscale crea red privada con WireGuard.

## Instalación
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

## Login
```bash
sudo tailscale up
```

## Estado
```bash
tailscale status
tailscale ip -4
```

## Subredes
```bash
sudo tailscale up --advertise-routes=192.168.1.0/24
```
