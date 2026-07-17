# rsync

## Backup local
```bash
rsync -av --delete /origen/ /destino/
```

## Remoto SSH
```bash
rsync -avz --delete -e ssh /origen/ usuario@servidor:/backup/
```

## Excluir
```bash
rsync -av --exclude='*.log' /origen/ /destino/
```

## Dry run
```bash
rsync -avn /origen/ /destino/
```
