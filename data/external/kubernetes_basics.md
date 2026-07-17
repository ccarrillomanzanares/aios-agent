# Kubernetes básico

## Contexto
```bash
kubectl config get-contexts
kubectl config use-context nombre
```

## Recursos
```bash
kubectl get nodes
kubectl get pods -A
kubectl get deployments
```

## Despliegue
```bash
kubectl create deployment nginx --image=nginx --replicas=3
kubectl scale deployment nginx --replicas=5
kubectl rollout status deployment/nginx
```

## k3s
```bash
curl -sfL https://get.k3s.io | sh -
```
