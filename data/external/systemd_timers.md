# systemd timers

## Timer
```ini
[Timer]
OnCalendar=daily
Persistent=true
```

## Service asociado
```ini
[Service]
Type=oneshot
ExecStart=/usr/local/bin/backup.sh
```

## Activar
```bash
sudo systemctl enable --now backup.timer
sudo systemctl list-timers
```
