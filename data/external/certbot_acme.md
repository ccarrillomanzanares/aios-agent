# Certbot / ACME - Certificados TLS gratuitos

Certbot es el cliente oficial de Let's Encrypt.

## Instalación
```bash
sudo apt install certbot
```

## Certificado standalone
```bash
sudo certbot certonly --standalone -d ejemplo.com -d www.ejemplo.com
```

## Certificado con Nginx
```bash
sudo certbot --nginx -d ejemplo.com -d www.ejemplo.com
```

## Renovación
```bash
sudo certbot renew --dry-run
```

## ACME.sh
```bash
curl https://get.acme.sh | sh
~/.acme.sh/acme.sh --issue -d ejemplo.com --nginx
```
