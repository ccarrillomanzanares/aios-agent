# sudoers y PAM

## sudoers
```bash
sudo visudo
```

Ejemplos:
```
usuario ALL=(ALL:ALL) ALL
%grupo ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart nginx
```

## Logs
```bash
cat /var/log/auth.log | grep sudo
```

## Límites
```
* soft nproc 2048
* hard nproc 4096
```
