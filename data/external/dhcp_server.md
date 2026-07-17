# Servidor DHCP

## isc-dhcp-server
```bash
sudo apt install isc-dhcp-server
```

/etc/dhcp/dhcpd.conf:
```
subnet 192.168.1.0 netmask 255.255.255.0 {
  range 192.168.1.100 192.168.1.200;
  option routers 192.168.1.1;
  option domain-name-servers 1.1.1.1;
}
```

## dnsmasq
```
dhcp-range=192.168.1.100,192.168.1.200,255.255.255.0,12h
```
