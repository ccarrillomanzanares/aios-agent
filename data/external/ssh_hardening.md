# SSH Hardening

## Configuración /etc/ssh/sshd_config
```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
AllowUsers usuario1 usuario2
X11Forwarding no
```

## Reiniciar
```bash
sudo systemctl restart sshd
```

## Claves
```bash
ssh-keygen -t ed25519
ssh-copy-id usuario@servidor
```
