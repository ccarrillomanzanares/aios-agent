# Kustomize

## Estructura
```
base/
  kustomization.yaml
overlays/
  production/
    kustomization.yaml
```

## Aplicar
```bash
kubectl apply -k overlays/production/
```
