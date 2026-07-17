# BIND9

## Instalación
```bash
sudo apt install bind9
```

## Opciones /etc/bind/named.conf.options
```
options {
    directory "/var/cache/bind";
    forwarders { 1.1.1.1; 8.8.8.8; };
    dnssec-validation auto;
};
```

## Zona /etc/bind/db.ejemplo.com
```
$TTL 604800
@ IN SOA ns.ejemplo.com. admin.ejemplo.com. (
    2024010101 ; Serial
    604800 ; Refresh
)
@ IN NS ns.ejemplo.com.
ns IN A 192.168.1.1
www IN A 192.168.1.10
```

## Verificar
```bash
sudo named-checkconf
sudo named-checkzone ejemplo.com /etc/bind/db.ejemplo.com
```
