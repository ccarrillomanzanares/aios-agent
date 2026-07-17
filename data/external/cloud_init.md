# cloud-init

## user-data
```yaml
#cloud-config
users:
  - name: admin
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-ed25519 AAAAC3...
package_update: true
packages:
  - nginx
runcmd:
  - systemctl enable --now nginx
```

## Logs
```bash
cat /var/log/cloud-init-output.log
```
