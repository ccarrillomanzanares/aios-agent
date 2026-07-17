# Terraform

## Comandos
```bash
terraform init
terraform plan
terraform apply
terraform destroy
```

## Ejemplo
```hcl
provider "aws" {
  region = "us-east-1"
}
resource "aws_instance" "web" {
  ami           = "ami-12345678"
  instance_type = "t3.micro"
}
```
