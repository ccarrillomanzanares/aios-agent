# ELK/EFK

## Elasticsearch
```bash
sudo apt install elasticsearch
sudo systemctl enable --now elasticsearch
curl http://localhost:9200
```

## Kibana
```bash
sudo apt install kibana
sudo systemctl enable --now kibana
```

## Filebeat
```bash
sudo apt install filebeat
sudo filebeat modules enable system nginx
```
