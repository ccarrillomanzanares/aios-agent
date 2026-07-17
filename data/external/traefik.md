# Traefik

## Docker Compose
```yaml
services:
  traefik:
    image: traefik:v3.0
    command:
      - --providers.docker=true
      - --entrypoints.web.address=:80
    ports:
      - 80:80
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

## Etiquetas
```yaml
labels:
  - traefik.enable=true
  - traefik.http.routers.miapp.rule=Host(`app.ejemplo.com`)
```
