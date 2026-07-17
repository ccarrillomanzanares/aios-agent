# cgroup v2

## Ver
```bash
mount | grep cgroup
cat /sys/fs/cgroup/cgroup.controllers
```

## Crear
```bash
sudo mkdir /sys/fs/cgroup/miapp
echo 100000000 | sudo tee /sys/fs/cgroup/miapp/cpu.max
echo 512M | sudo tee /sys/fs/cgroup/miapp/memory.max
```

## systemd
```bash
systemctl set-property nginx.service CPUQuota=50%
systemctl set-property nginx.service MemoryMax=512M
```
