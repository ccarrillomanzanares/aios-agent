# WireGuard - VPN moderno

WireGuard usa criptografía moderna.

## Instalación
```bash
sudo apt install wireguard
```

## Claves
```bash
wg genkey | tee privatekey | wg pubkey > publickey
```

## Servidor /etc/wireguard/wg0.conf
```ini
[Interface]
PrivateKey = <server_private>
Address = 10.0.0.1/24
ListenPort = 51820

[Peer]
PublicKey = <client_public>
AllowedIPs = 10.0.0.2/32
```

## Activar
```bash
sudo wg-quick up wg0
sudo systemctl enable --now wg-quick@wg0
sudo wg show
```
