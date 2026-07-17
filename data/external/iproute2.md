# iproute2

`ip` reemplaza ifconfig, route, arp.

## Interfaces
```bash
ip link show
ip link set eth0 up
ip addr show
ip addr add 192.168.1.10/24 dev eth0
```

## Rutas
```bash
ip route show
ip route add default via 192.168.1.1
```

## Vecinos
```bash
ip neigh show
```

## VLAN
```bash
ip link add link eth0 name eth0.10 type vlan id 10
```
