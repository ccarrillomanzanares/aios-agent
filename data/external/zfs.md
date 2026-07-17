# ZFS

## Pool
```bash
sudo zpool create tank /dev/sdb
sudo zpool create tank mirror /dev/sdb /dev/sdc
```

## Datasets
```bash
sudo zfs create tank/apps
sudo zfs set compression=lz4 tank/apps
```

## Snapshots
```bash
sudo zfs snapshot tank/apps@antes_update
sudo zfs rollback tank/apps@antes_update
```

## Scrub
```bash
sudo zpool scrub tank
```
