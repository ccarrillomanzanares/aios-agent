# auditd - Auditoría del sistema Linux

auditd registra eventos de seguridad.

## Instalación
```bash
sudo apt install auditd audispd-plugins
sudo systemctl enable --now auditd
```

## Reglas
```bash
sudo auditctl -w /etc/passwd -p wa -k passwd_changes
sudo auditctl -a always,exit -F arch=b64 -S setuid -k privilege_escalation
```

## Búsqueda
```bash
sudo ausearch -k passwd_changes
sudo aureport --auth --summary
```

## Persistencia
```bash
echo '-w /etc/passwd -p wa -k passwd_changes' | sudo tee -a /etc/audit/rules.d/custom.rules
sudo augenrules --load
```
