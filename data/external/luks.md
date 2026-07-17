# LUKS - Cifrado

## Crear
```bash
sudo cryptsetup luksFormat /dev/sdb1
sudo cryptsetup open /dev/sdb1 datos_enc
sudo mkfs.ext4 /dev/mapper/datos_enc
sudo mount /dev/mapper/datos_enc /mnt/enc
```

## Cerrar
```bash
sudo umount /mnt/enc
sudo cryptsetup close datos_enc
```
