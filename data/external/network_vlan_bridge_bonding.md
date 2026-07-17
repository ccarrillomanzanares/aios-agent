# VLAN, bonding y bridge

## VLAN
```bash
sudo ip link add link eth0 name eth0.10 type vlan id 10
sudo ip addr add 192.168.10.10/24 dev eth0.10
sudo ip link set eth0.10 up
```

## Bonding
```bash
sudo modprobe bonding mode=802.3ad miimon=100
sudo ip link add bond0 type bond mode 802.3ad
sudo ip link set eth0 master bond0
sudo ip link set eth1 master bond0
```

## Bridge
```bash
sudo ip link add name br0 type bridge
sudo ip link set eth0 master br0
sudo ip link set br0 up
```
