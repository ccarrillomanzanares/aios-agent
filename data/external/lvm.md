# LVM

## Crear
```bash
sudo pvcreate /dev/sdb
sudo vgcreate vg_datos /dev/sdb
sudo lvcreate -L 50G -n lv_apps vg_datos
sudo mkfs.ext4 /dev/vg_datos/lv_apps
sudo mount /dev/vg_datos/lv_apps /apps
```

## Extender
```bash
sudo lvextend -L +10G /dev/vg_datos/lv_apps
sudo resize2fs /dev/vg_datos/lv_apps
```

## Snapshot
```bash
sudo lvcreate -L 5G -s -n snap_antes_update /dev/vg_datos/lv_apps
```
