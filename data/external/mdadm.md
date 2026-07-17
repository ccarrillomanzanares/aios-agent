# mdadm - RAID

## Crear RAID 1
```bash
sudo mdadm --create /dev/md0 --level=1 --raid-devices=2 /dev/sdb /dev/sdc
sudo mkfs.ext4 /dev/md0
sudo mount /dev/md0 /mnt/raid1
```

## Estado
```bash
cat /proc/mdstat
sudo mdadm --detail /dev/md0
```

## Guardar config
```bash
sudo mdadm --detail --scan | sudo tee -a /etc/mdadm/mdadm.conf
sudo update-initramfs -u
```
