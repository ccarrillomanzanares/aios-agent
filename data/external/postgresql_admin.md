# PostgreSQL básico

## Instalación
```bash
sudo apt install postgresql
sudo systemctl enable --now postgresql
```

## Conexión
```bash
sudo -u postgres psql
```

## Crear usuario y base
```sql
CREATE USER app WITH PASSWORD 'secreto';
CREATE DATABASE app OWNER app;
```

## Backup
```bash
pg_dump -U postgres -Fc mi_db > mi_db.dump
pg_restore -U postgres -d mi_db mi_db.dump
```
