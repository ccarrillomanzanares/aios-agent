# MySQL / MariaDB básico

## Instalación
```bash
sudo apt install mariadb-server
sudo mysql_secure_installation
```

## Conexión
```bash
sudo mysql -u root
```

## Crear
```sql
CREATE USER 'app'@'localhost' IDENTIFIED BY 'secreto';
CREATE DATABASE app;
GRANT ALL PRIVILEGES ON app.* TO 'app'@'localhost';
```

## Backup
```bash
mysqldump -u root -p app > app.sql
mysql -u root -p app < app.sql
```
