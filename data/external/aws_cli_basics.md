# AWS CLI básico

## Configuración
```bash
aws configure
```

## EC2
```bash
aws ec2 describe-instances
aws ec2 start-instances --instance-ids i-1234567890
```

## S3
```bash
aws s3 ls
aws s3 cp archivo.txt s3://mi-bucket/
aws s3 sync ./local s3://mi-bucket/backup/
```

## CloudWatch
```bash
aws logs tail /aws/lambda/mi-funcion --follow
```
