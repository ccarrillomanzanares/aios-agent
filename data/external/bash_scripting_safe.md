# Guía de scripting seguro en Bash para SRE

## Crear un script

Usa un heredoc para crear el archivo, shebang correcto y permisos de ejecución:

```bash
cat > /tmp/mi_script.sh << 'EOF'
#!/bin/bash
set -euo pipefail

echo "Hola mundo"
EOF
chmod +x /tmp/mi_script.sh
```

Reglas de seguridad:
- Siempre `set -euo pipefail`.
- Usa `timeout` para procesos largos.
- No escribas en `/proc`, `/sys`, `/dev` salvo que sea estrictamente necesario.
- Valida variables con comillas: `"$VAR"`.
- Evita `rm -rf` sin confirmación.
- Para bucles con pausas, usa `sleep` y un mecanismo de salida, o `timeout`.

## Ejecutar un script

```bash
bash /tmp/mi_script.sh
```

## Detener un proceso largo

```bash
pkill -f /tmp/mi_script.sh
```

## Listar archivos del directorio

```bash
ls -la
```
