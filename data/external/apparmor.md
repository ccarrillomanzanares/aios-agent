# AppArmor - Control de acceso

AppArmor restringe procesos con perfiles.

## Estado
```bash
sudo aa-status
```

## Modos
```bash
sudo aa-complain /usr/bin/nginx
sudo aa-enforce /usr/bin/nginx
```

## Crear perfil
```bash
sudo aa-genprof /ruta/binario
```

## Recargar
```bash
sudo apparmor_parser -r /etc/apparmor.d/usr.bin.nginx
```
