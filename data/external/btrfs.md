# Btrfs

## Crear
```bash
sudo mkfs.btrfs /dev/sdb
sudo mount /dev/sdb /mnt
```

## Subvolúmenes
```bash
sudo btrfs subvolume create /mnt/apps
sudo btrfs subvolume snapshot /mnt/apps /mnt/apps_snap
```

## Compresión
```bash
sudo btrfs property set /mnt/apps compression zstd
```
