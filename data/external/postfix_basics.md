# Postfix básico

## Instalación
```bash
sudo apt install postfix mailutils
```

## Estado
```bash
sudo systemctl status postfix
sudo postqueue -p
```

## Relay
```
relayhost = [smtp.gmail.com]:587
smtp_tls_security_level = encrypt
```

## Aliases
```
root: admin@ejemplo.com
```
