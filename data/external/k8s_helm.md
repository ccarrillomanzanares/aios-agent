# Helm

## Instalación
```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

## Comandos
```bash
helm repo add stable https://charts.helm.sh/stable
helm repo update
helm install mi-nginx stable/nginx-ingress
helm list
helm uninstall mi-nginx
```
