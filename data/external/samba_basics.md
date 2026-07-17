# Samba

## Instalación
```bash
sudo apt install samba
```

## smb.conf
```ini
[compartido]
path = /srv/samba/compartido
valid users = @smbusers
read only = no
```

## Usuario
```bash
sudo smbpasswd -a carlos
```
