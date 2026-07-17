# smartmontools

## Instalación
```bash
sudo apt install smartmontools
```

## Información
```bash
sudo smartctl -a /dev/sda
```

## Tests
```bash
sudo smartctl -t short /dev/sda
sudo smartctl -t long /dev/sda
```

## smartd
```
/dev/sda -a -o on -S on -s (S/../.././02|L/../../6/03)
```
