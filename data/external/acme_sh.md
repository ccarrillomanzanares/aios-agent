# acme.sh

## Instalación
```bash
curl https://get.acme.sh | sh
```

## Emitir
```bash
~/.acme.sh/acme.sh --issue -d ejemplo.com --nginx
```

## Instalar
```bash
~/.acme.sh/acme.sh --install-cert -d ejemplo.com   --key-file /etc/nginx/ssl/ejemplo.key   --fullchain-file /etc/nginx/ssl/ejemplo.crt   --reloadcmd "systemctl reload nginx"
```
