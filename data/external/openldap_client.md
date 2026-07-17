# OpenLDAP cliente

## Instalación
```bash
sudo apt install ldap-utils libnss-ldap libpam-ldap
```

## Configuración
```
base dc=ejemplo,dc=com
uri ldap://ldap.ejemplo.com
```

## Test
```bash
ldapsearch -x -H ldap://ldap.ejemplo.com -b dc=ejemplo,dc=com uid=carlos
```
