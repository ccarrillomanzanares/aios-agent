# BorgBackup

## Inicializar
```bash
borg init --encryption=repokey /mnt/backup/borg
```

## Backup
```bash
borg create /mnt/backup/borg::hoy /home /etc
```

## Listar
```bash
borg list /mnt/backup/borg
```

## Extraer
```bash
borg extract /mnt/backup/borg::hoy etc/nginx/nginx.conf
```
