# OpenVPN - VPN tradicional

OpenVPN usa TLS.

## Instalación
```bash
sudo apt install openvpn easy-rsa
```

## CA con Easy-RSA
```bash
make-cadir ~/openvpn-ca
cd ~/openvpn-ca
./easyrsa init-pki
./easyrsa build-ca nopass
./easyrsa gen-req server nopass
./easyrsa sign-req server server
./easyrsa gen-crl
```

## Activar
```bash
sudo systemctl enable --now openvpn@server
```
