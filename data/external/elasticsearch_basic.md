# Elasticsearch básico

## Cluster health
```bash
curl http://localhost:9200/_cluster/health?pretty
```

## Índices
```bash
curl -X PUT http://localhost:9200/mi_indice
curl -X DELETE http://localhost:9200/mi_indice
```

## Documentos
```bash
curl -X POST http://localhost:9200/mi_indice/_doc/1 -H 'Content-Type: application/json' -d '{"msg":"hola"}'
```
