# Restic

## Inicializar
```bash
restic init --repo /mnt/backup/restic
```

## Backup
```bash
restic -r /mnt/backup/restic backup /home /etc
```

## Snapshots
```bash
restic -r /mnt/backup/restic snapshots
```

## Restaurar
```bash
restic -r /mnt/backup/restic restore latest --target /tmp/restore
```

## Mantenimiento
```bash
restic -r /mnt/backup/restic forget --keep-daily 7 --keep-weekly 4
restic -r /mnt/backup/restic prune
```
