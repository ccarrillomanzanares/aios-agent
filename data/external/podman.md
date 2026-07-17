# Podman

## Sin daemon
```bash
podman run -d -p 8080:80 --name web nginx:alpine
podman ps
podman exec -it web sh
```

## Pods
```bash
podman pod create --name miapp -p 8080:80
podman run -d --pod miapp --name web nginx:alpine
```
