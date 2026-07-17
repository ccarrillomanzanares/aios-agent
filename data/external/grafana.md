# Grafana

## Instalación
```bash
sudo apt install grafana
sudo systemctl enable --now grafana-server
```

## Acceso
http://localhost:3000 admin/admin

## Datasource Prometheus
```bash
curl -X POST http://admin:admin@localhost:3000/api/datasources   -H 'Content-Type: application/json'   -d '{"name":"Prometheus","type":"prometheus","url":"http://localhost:9090"}'
```
