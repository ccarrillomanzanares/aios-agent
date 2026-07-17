# UFW - Uncomplicated Firewall

UFW es un frontend de iptables/nftables.

## Estado
```bash
sudo ufw status verbose
sudo ufw enable
sudo ufw disable
```

## Políticas
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
```

## Reglas comunes
```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw limit 22/tcp
```

## Borrar reglas
```bash
sudo ufw status numbered
sudo ufw delete 2
```
