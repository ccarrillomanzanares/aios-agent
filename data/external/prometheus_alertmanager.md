# Prometheus Alertmanager

## Configuración /etc/prometheus/alertmanager.yml
```yaml
global:
  smtp_smarthost: 'smtp.ejemplo.com:587'
route:
  receiver: 'equipo'
receivers:
  - name: 'equipo'
    email_configs:
      - to: 'sre@ejemplo.com'
```

## Regla Prometheus
```yaml
- alert: AltaCPU
  expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
  for: 5m
```
