# Docker Compose

## Ejemplo
```yaml
services:
  web:
    image: nginx:alpine
    ports:
      - "80:80"
  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: secreto
```

## Comandos
```bash
docker compose up -d
docker compose down
docker compose logs -f
```
