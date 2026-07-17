# Lynis - Auditoría de seguridad

## Instalación
```bash
sudo apt install lynis
```

## Escaneo
```bash
sudo lynis audit system
sudo lynis audit system --quick
```

## Reporte
```bash
cat /var/log/lynis-report.dat
```
