# SFTP chroot

## Crear usuario
```bash
sudo groupadd sftpusers
sudo useradd -g sftpusers -d /srv/sftp/usuario -s /sbin/nologin usuario
sudo mkdir -p /srv/sftp/usuario/upload
sudo chown root:root /srv/sftp/usuario
sudo chown usuario:sftpusers /srv/sftp/usuario/upload
```

## sshd_config
```
Match Group sftpusers
    ChrootDirectory /srv/sftp/%u
    ForceCommand internal-sftp
```
