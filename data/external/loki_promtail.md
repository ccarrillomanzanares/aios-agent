# Loki + Promtail

## Loki Docker
```bash
docker run -d -p 3100:3100 grafana/loki:latest
```

## Promtail config
```yaml
clients:
  - url: http://localhost:3100/loki/api/v1/push
scrape_configs:
  - job_name: journal
    journal:
      max_age: 12h
```
