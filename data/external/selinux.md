# SELinux - Security-Enhanced Linux

SELinux aplica políticas de acceso obligatorio.

## Modos
```bash
getenforce
sudo setenforce 0
sudo setenforce 1
```

## Contextos
```bash
ls -Z /var/www/html
sudo chcon -t httpd_sys_content_t /var/www/html/index.html
sudo restorecon -Rv /var/www/html
```

## Booleanos
```bash
getsebool -a | grep httpd
sudo setsebool httpd_can_network_connect on
```

## Logs
```bash
sudo ausearch -m AVC -ts recent
```
