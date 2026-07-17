# NFS

## Servidor
```bash
sudo apt install nfs-kernel-server
```

/etc/exports:
```
/mnt/compartida 192.168.1.0/24(rw,sync,no_subtree_check)
```

```bash
sudo exportfs -ra
```

## Cliente
```bash
sudo apt install nfs-common
sudo mount -t nfs 192.168.1.10:/mnt/compartida /mnt/nfs
```
