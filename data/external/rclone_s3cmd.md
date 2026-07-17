# rclone y s3cmd

## rclone
```bash
rclone config
rclone sync /local s3:mi-bucket/backup
rclone mount s3:mi-bucket /mnt/s3 --daemon
```

## s3cmd
```bash
s3cmd ls
s3cmd put archivo.txt s3://mi-bucket/
s3cmd sync ./local s3://mi-bucket/backup
```
