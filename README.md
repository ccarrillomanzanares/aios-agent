# AIOS Agent v3.3

Agente SRE semiautónomo con function calling, diseñado para ejecutarse en local (CPU), cloud o dentro de la ISO AIOS LFS live.

## Arquitectura

```
┌──────────────────────────────────────────────────┐
│                    setup.py                        │
│  (wizard de primer uso, modo local fijado,         │
│   opción INSTALL TO DISK)                          │
├──────────────────────────────────────────────────┤
│                    chat.py                         │
│  (CLI interactivo, auto-arranque de llama-server,  │
│   wrapper EOF/errores)                             │
├──────────────────────────────────────────────────┤
│                    agent.py                        │
│  (bucle de function calling: llama.cpp API +       │
│   tools + memoria procedural + compresión)         │
├──────────────────────────────────────────────────┤
│  tools.py     memory.py    process.py  playbook.py │
│  (11 tools)   (caché)      (PTY)       (YAML)     │
└──────────────────────────────────────────────────┘
```

## Instalación

### Local (CPU, recomendado)

```bash
git clone https://github.com/ccarrillomanzanares/aios-agent
cd aios-agent
pip install -r requirements.txt

# Descargar modelo (manual, antes del primer arranque)
python3 -c "from huggingface_hub import hf_hub_download; hf_hub_download('bartowski/Qwen_Qwen3-8B-GGUF', 'Qwen_Qwen3-8B-Q4_K_M.gguf', local_dir='models/')"

# Ejecutar agente — chat.py levanta llama-server automáticamente
python3 chat.py
```

> **Novedad v3.3:** ya no hace falta iniciar `llama-server` a mano. `chat.py` detecta si el servidor local está corriendo y, en caso contrario, lo arranca él mismo con `LD_LIBRARY_PATH` apuntando a `/usr/local/lib/llama`, esperando hasta 30 segundos a que responda.

### ISO AIOS LFS

El agente está preinstalado en la ISO AIOS LFS live. Ver `README-aios-lfs-v8.md` para la ISO que incluye este agente.

> **Modelo en la ISO:** la imagen ISO no incluye ningún modelo GGUF por defecto. El modo **cloud** funciona out-of-the-box siempre que haya configuración de API. El modo **local** requiere descargar manualmente un modelo GGUF y apuntar `config.yaml` a él.

### Instalación a disco desde la ISO AIOS LFS

La ISO live incluye el instalador `aios-install` para escribir el sistema en disco duro. `setup.py` expone la opción **4: INSTALL TO DISK**:

1. Iniciar la ISO AIOS LFS y abrir una terminal.
2. Ejecutar `setup.py` y elegir la opción **`4) INSTALL TO DISK`**.
3. El setup lanza el instalador `aios-install`.
4. Al terminar la instalación, el setup pregunta si se desea reiniciar (`reboot`).

|**Flujo de setup.py:**|

```text
1) Configure AIOS
2) Start AIOS (local)
3) Exit
4) INSTALL TO DISK
```

- Seleccionar `4` ejecuta `/usr/local/bin/aios-install`.
- Tras completar la instalación, setup solicita confirmación para reiniciar el sistema.

#### Fix v8: GRUB gráfico cuelga en VirtualBox tras instalación a disco

> **Problema:** en instalaciones a disco sobre VirtualBox, el primer arranque se colgaba mostrando `Cargando Linux 6.18.10-lfs ...` después de que la instalación terminara correctamente.
>
> **Causa raíz:** `aios-install` generaba el menú GRUB mediante `grub-mkconfig` dentro del chroot. El `grub.cfg` resultante incluía `load_video`, `insmod all_video`, `gfxpayload=keep` y `terminal_output gfxterm`, que bloquean el boot en VirtualBox.
>
> **Solución v3.3:** `aios-install` ya no ejecuta `grub-mkconfig`. En su lugar escribe un `grub.cfg` fijo en modo texto, simple, sin UUID y sin referencias a "Arch Linux":
>
> ```cfg
> set default=0
> set timeout=5
> menuentry "AIOS LFS" {
>     linux /boot/vmlinuz-6.18.10-lfs root=/dev/sda2 rw nokaslr console=tty0 loglevel=6
> }
> ```
>
> La ISO live seguía arrancando correctamente porque `grub-mkrescue` del host Ubuntu genera un menú minimalista en modo texto. El fallo solo afectaba al `grub.cfg` generado por `grub-mkconfig` en el sistema instalado.

## Boot flow en la ISO AIOS LFS

El arranque gráfico del agente sigue este flujo secuencial:

1. **login** — autenticación del usuario de la sesión.
2. **aios-session** — script de arranque de sesión (`scripts/aios-session`) que:
   - lanza el setup inicial si no existe `~/.aios/config.yaml`;
   - una vez configurado, inicia **Xorg primero**, luego **i3** con `exec` condicional;
   - `i3` lanza un `xterm` que ejecuta el agente (`aios` / `chat.py`).

El servicio de modelo (`aios-llama.service`) no arranca por defecto en boot; se activa durante el setup cuando se elige modo `local` o `hybrid`.

### Cambios v3.3 en `chat.py` — auto-arranque de llama-server

A partir de v3.3 `chat.py` integra `_start_local_model()` para el modo `local`/`hybrid`:

1. Lee `~/.aios/config.yaml`.
2. Si `mode` es `local` o `hybrid`, comprueba si `llama-server` ya responde en `http://127.0.0.1:8083`.
3. Si no responde, lanza `llama-server` con el modelo configurado y `LD_LIBRARY_PATH=/usr/local/lib/llama`.
4. Espera hasta 30 segundos (poll cada 0.5 s) a que el endpoint `/health` devuelva HTTP 200.
5. Si el modelo no existe, informa al usuario y vuelve al menú de setup.

Esto elimina el paso manual de arrancar `llama-server` antes de ejecutar `chat.py`.

## Permisos

El directorio del agente debe pertenecer al grupo `wheel` y tener el propietario `aios` para que `chat.py` pueda escribir el directorio `data/` (logs, memoria y caché):

```bash
sudo chown -R aios:wheel /usr/local/bin/aios-agent
sudo chmod -R g+w /usr/local/bin/aios-agent/data
```

Si el usuario que ejecuta el agente no está en el grupo `wheel`, añadirlo antes de iniciar la sesión:

```bash
sudo usermod -aG wheel "$USER"
```

## Configuración

Primer arranque: `scripts/aios-session` ejecuta el wizard de setup automáticamente si falta `~/.aios/config.yaml`.

Fichero de configuración: `~/.aios/config.yaml`

```yaml
mode: local
local:
  model: Qwen_Qwen3-8B-Q4_K_M.gguf
  model_name: Qwen3-8B-Instruct
  threads: 14
  context: 32768
cloud:
  provider: null
  model: null
```

### Modos

- **local**: usa modelo local via llama.cpp en :8083
- **cloud**: usa API externa (DeepSeek, OpenAI, Anthropic, etc.)
- **hybrid**: local para simple, cloud para complejo

## Herramientas (function calling)

| Tool | Descripción |
|---|---|
| `run_command` | Ejecuta comandos shell (con bloqueo de peligrosos + confirmación) |
| `read_file` | Lee archivos |
| `write_file` | Escribe archivos |
| `git_operation` | Operaciones git |
| `mcp_call` | Llamadas a servidores MCP |
| `run_playbook` | Ejecuta playbooks YAML |
| `process_start` | Inicia proceso interactivo (PTY) |
| `process_send` | Envía entrada a proceso interactivo |
| `process_close` | Cierra proceso interactivo |
| `process_list` | Lista procesos activos |
| `web_search` | Búsqueda web via Firecrawl |

## Scripts auxiliares

| Script | Descripción |
|---|---|
| `scripts/aios-session` | Arranque de sesión gráfica en la ISO: detecta si existe `~/.aios/config.yaml`, ejecuta setup en caso contrario, luego lanza `startx` → `i3` → `xterm` con el agente |
| `scripts/launch_llama.py` | Lanzador legacy de llama-server; `chat.py` lo auto-arranca en v3.3, por lo que el servicio sigue siendo útil en background/ISO |
| `scripts/firstboot.sh` | Wizard de primer arranque (setup + enable servicios) |
| `aios-install` | Instala ISO AIOS LFS a disco duro |
| `setup.py` | Wizard de instalación y arranque en la ISO. Modo local fijado a Qwen3-8B, sin descarga automática, sin selección de modelo. Opciones: `1) Configure AIOS`, `2) Start AIOS (local)`, `3) Exit`, `4) INSTALL TO DISK`. |

### setup.py — Cambios v3.3

- **Modelo único:** solo permite Qwen3-8B (`Qwen_Qwen3-8B-Q4_K_M.gguf`). Se eliminó la selección entre Qwen2.5-7B y Qwen3-8B.
- **Sin descarga automática:** si el modelo no existe en `/home/ccmai/models/` o `/usr/local/share/aios/models/`, `setup.py` informa del fallo y **vuelve al menú principal** en lugar de intentar descargarlo.
- **Menú simplificado:** opciones `1-4` claras; `2) Start AIOS (local)` arranca el chat directamente.
- **Validación de API key:** detecta si la clave introducida está vacía, tiene formato inválido o ha caducado, y solicita reintroducirla.
- **Bucle de reintento:** ante fallo de conectividad con el proveedor cloud, permite reintentar antes de abortar.
- **Fix de backspace en readline:** corrige el comportamiento de la tecla Backspace en terminales con locales UTF-8.
- **Opción 4: INSTALL TO DISK** sigue presente y lanza `aios-install`.

```text
$ sudo setup.py
Seleccione una opción:
  1) Configure AIOS
  2) Start AIOS (local)
  3) Exit
  4) INSTALL TO DISK
Opción: 4
[aios-install] Instalando AIOS LFS al disco...
[aios-install] Instalación completada.
¿Desea reiniciar ahora? [s/N]:
```

> **Nota:** La opción 4 requiere privilegios de root para escribir en el disco de destino. Se recomienda ejecutar `setup.py` con `sudo` cuando se vaya a usar.
>
> **Fix v8 (GRUB):** el instalador `aios-install` escribe ahora un `grub.cfg` fijo en modo texto, reemplazando la generación con `grub-mkconfig` que colgaba en VirtualBox. Ver sección [Fix v8: GRUB gráfico cuelga en VirtualBox tras instalación a disco](#fix-v8-grub-gráfico-cuelga-en-virtualbox-tras-instalación-a-disco).

### chat.py — Auto-arranque del modelo local

La función `_start_local_model()` de `chat.py` automatiza el inicio de `llama-server`:

1. Comprueba si el endpoint `http://127.0.0.1:8083/health` ya responde.
2. Si no responde, construye el comando con el modelo configurado:
   ```bash
   /usr/local/bin/llama-server -m <modelo> --host 127.0.0.1 --port 8083 \
     -c <context> -t <threads> --jinja
   ```
   y lo lanza con `LD_LIBRARY_PATH=/usr/local/lib/llama`.
3. Espera activamente hasta 30 s a que `/health` devuelva `HTTP 200`.
4. Si el modelo no existe, muestra un mensaje claro y retorna al menú principal de `setup.py`.

### launch_llama.py — Lanzador legacy

`scripts/launch_llama.py` sigue siendo el ejecutable usado por `aios-llama.service`. A partir de v3.3, su principal responsabilidad es mantener `LD_LIBRARY_PATH=/usr/local/lib/llama` para que `llama-server` encuentre `libllama-server-impl.so` cuando no haya configurado `ldconfig`.

## Configuración final del sistema en ISO AIOS LFS

Estas notas describen el estado de configuración del sistema base sobre el que se ejecuta el agente en la ISO live y en la instalación a disco.

### Fuente consola

La consola virtual (TTY) de la ISO AIOS LFS usa la fuente **Terminus 12px** (`ter-112n`) para mejorar la legibilidad en alta resolución:

```bash
# /etc/vconsole.conf
FONT=ter-112n
```

### ldconfig / ld.so.conf.d

A partir de v3.3 se configura el directorio de librerías compartidas de llama.cpp para que `llama-server` y `chat.py` no dependan de exportar `LD_LIBRARY_PATH`:

```bash
# /etc/ld.so.conf.d/llama.conf
/usr/local/lib/llama
```

Tras crear el archivo, ejecutar:

```bash
ldconfig
```

Esto permite que `llama-server` encuentre `libllama-server-impl.so` sin necesidad de `LD_LIBRARY_PATH`, tanto en la ISO live como en la instalación a disco. `launch_llama.py` y `chat.py` siguen exportando `LD_LIBRARY_PATH` como medida defensiva.

### Dependencias del sistema

La imagen AIOS LFS mantiene la configuración estándar de BLFS/LFS para los subsistemas de autenticación y resolución de nombres:

- **`nsswitch.conf`** — archivo de configuración de GNU libc estándar (`/etc/nsswitch.conf`).
  - Orden de resolución de usuarios/grupos: `files` primero, luego servicios opcionales como `systemd` o `ldap` si se habilitan.
  - DNS: `hosts: files dns` por defecto.
  - No se requieren modificaciones especiales para el agente.

- **PAM (Pluggable Authentication Modules)** — configuración BLFS estándar en `/etc/pam.d/`.
  - `login`, `su`, `sudo`, `passwd` y otros gestores de sesión usan módulos PAM habituales (`pam_unix.so`, `pam_wheel.so`, etc.).
  - La política por defecto requiere autenticación con contraseña para acciones privilegiadas.

### PATH + secure_path

En la ISO y tras instalación a disco, `PATH` incluye explícitamente:

```bash
/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

`sudoers` usa `secure_path` con `/usr/sbin:/sbin:/bin` para que `aios-install` y otros scripts de mantenimiento encuentren `grub-install`, `mke2fs`, `parted`, etc.

### Instalador a disco

El instalador `aios-install` v1.0.1 incluye los siguientes ajustes de robustez:

- **Formateo con rutas completas:** usa `/usr/sbin/mke2fs -t ext4` en lugar del wrapper `mkfs.ext4`, evitando depender de symlinks que puedan faltar en el entorno live.
- **Instalación de GRUB con rutas completas:** invoca `/usr/sbin/grub-install` directamente, **sin `--force`**.
- **GRUB entry point 0x9000:** `grub-install` funciona sin `--force` porque el GRUB de la ISO está compilado con el fix de linker (ver sección GRUB más abajo).
- **GRUB.cfg fijo en modo texto:** reemplaza `grub-mkconfig` por un `grub.cfg` simple que evita módulos gráficos problemáticos en VirtualBox.

### GRUB compilado desde LFS 13.0-systemd

La ISO AIOS LFS y la instalación a disco usan un **GRUB 2.12/2.14 compilado desde fuentes en LFS 13.0-systemd**, no el GRUB de una distribución binaria. Esto garantiza que el bootloader está alineado con el toolchain y la configuración del sistema.

**Build con fix de linker (entry point `0x9000`)**

Durante la compilación de GRUB en LFS 13.0-systemd, el linker del toolchain puede producir un binario cuyo entry point se desplace de `0x9000`, causando un fallo crítico al intentar generar la imagen de arranque (`grub-mkrescue`, `grub-install` o el build del paquete fallan con un error de entry point inesperado).

El fix aplicado consiste en neutralizar la opción `--image-base` del linker durante `configure`, forzando el entry point esperado:

```bash
cd grub-2.14
sed 's/--image-base/--nonexist-linker-option/' -i configure
./configure --prefix=/usr --sysconfdir=/etc --disable-efiemu --disable-werror
make -j$(nproc)
make install
```

Verificación:

```bash
readelf -h /usr/lib/grub/i386-pc/kernel.img | grep Entry
# Entry point address: 0x9000
```

Resultado:

- `grub-mkrescue` genera correctamente la imagen ISO híbrida.
- `grub-install` (invocado como `/usr/sbin/grub-install` en `aios-install`) instala el bootloader en el disco de destino sin `--force` y sin fallos de stage1/stage2.
- El sistema arranca tanto en modo BIOS/Legacy como en modo UEFI cuando se añaden las rutas de módulos EFI correspondientes.

> **Nota:** para generar la ISO final se utiliza `grub-mkrescue` del **host** (por ejemplo Ubuntu), no directamente `xorriso`. `grub-mkrescue` requiere los módulos EFI y `mtools` (`apt install mtools` o instalar con Sven).

### ISO build con modelos >4 GB — `grub-mkrescue -iso-level 3`

A partir de v3.3, la generación de la ISO distingue dos escenarios:

- **ISO sin modelo GGUF:** se genera con `grub-mkrescue` normal.
- **ISO con modelo GGUF incluido:** si la imagen supera los ~4 GB, se añade el flag `-iso-level 3` a `grub-mkrescue` para soportar ficheros grandes (>4 GB) y evitar errores de `xorriso` al empaquetar el modelo.

Ejemplo:

```bash
# Sin modelo (ISO pequeña)
sudo grub-mkrescue -o aios-lfs.iso /tmp/iso

# Con modelo Qwen3-8B (~4.7 GB)
sudo grub-mkrescue -iso-level 3 -o aios-lfs-qwen3-8b.iso /tmp/iso
```

### Paquetes necesarios en la ISO

Para que `aios-install` y el entorno live funcionen correctamente, la ISO debe incluir al menos estos paquetes del sistema base:

| Paquete | Motivo |
|---|---|
| `parted` | Particionado del disco de destino en `aios-install` |
| `rsync` | Copia eficiente del sistema live al disco instalado |
| `e2fsprogs` | Formateo ext4 (`mke2fs`, `e2label`, etc.) |
| `terminus-font` | Fuente `ter-112n` configurada en `/etc/vconsole.conf` |
| `mtools` | Requerido por `grub-mkrescue` del host para ISO híbrida |
| `grub` (compilado LFS) | Bootloader con entry point 0x9000 |

### Servicios systemd en la ISO

```
/usr/lib/systemd/system/
├── aios-llama.service    # llama-server (disabled at boot, se activa en setup si local/híbrido)
├── aios-agent.service    # chat.py interactivo (disabled, lo lanza i3)
├── dbus.service          # D-Bus activado en live e instalación
└── ldconfig.service      # masked en live para evitar regenerar caché en cada boot
```

Cambios v3.3:

- **`chat.py` auto-arranque:** `chat.py` inicia `llama-server` automáticamente si no está corriendo.
- **`ld.so.conf.d/llama.conf`:** ldconfig conoce `/usr/local/lib/llama` para `libllama-server-impl.so`.
- **GRUB fijo en modo texto:** `aios-install` genera `grub.cfg` fijo para evitar cuelgue en VirtualBox.
- **`setup.py` simplificado:** modo local fijado a Qwen3-8B; sin descarga automática; vuelve al menú si falta el modelo.
- **ISO build con `-iso-level 3`:** soporta ISOs con modelo >4 GB.

Cambios v3.2:

- **dbus.service creado y habilitado:** permite que aplicaciones gráficas y servicios como el agente se comuniquen a través de D-Bus.
- **ldconfig.service masked para live:** evita que systemd ejecute `ldconfig` en cada arranque de la ISO, ahorrando tiempo de boot.
- `sshd` está deshabilitado en la ISO, sin host keys fijas; si se necesita, se arranca manualmente (`/etc/rc.d/init.d/sshd start`) y se regeneran las keys al primer uso.
- Firefox se ha eliminado del autostart gráfico; no se abre automáticamente al iniciar sesión.

### sudo

En la **ISO live**, el usuario `aios` pertenece al grupo `wheel` y `sudo` se configura con **NOPASSWD** para el grupo `wheel`:

```sudoers
%wheel ALL=(ALL:ALL) NOPASSWD: ALL
```

Esto permite que el agente y los scripts del sistema (`setup.py`, `aios-install`) ejecuten comandos privilegiados sin interacción del usuario.

> **Instalación a disco:** una vez copiado el sistema al disco duro con `aios-install`, se recomienda revisar esta política. En un sistema instalado se puede restringir a comandos específicos o exigir contraseña según la política de seguridad deseada.

### Sin modelo en ISO

La imagen ISO **no incluye ningún modelo GGUF** por defecto. Esto reduce el tamaño de la ISO y evita problemas de licenciamiento/descarga masiva.

- **Modo cloud:** funciona inmediatamente si se proporciona la configuración de API externa.
- **Modo local/híbrido:** el usuario debe descargar manualmente un modelo GGUF (por ejemplo, `Qwen_Qwen3-8B-Q4_K_M.gguf`) y colocarlo en `/usr/local/share/aios/models/`, o en la ruta indicada en `~/.aios/config.yaml`.

## Rutas en ISO

| Componente | Ruta |
|---|---|
| Repo agente | `/usr/local/bin/aios-agent/` |
| llama-server | `/usr/local/bin/llama-server` |
| Librerías | `/usr/local/lib/llama/` |
| ld.so.conf.d | `/etc/ld.so.conf.d/llama.conf` |
| Modelo | `/usr/local/share/aios/models/` |
| Instalador | `/usr/local/bin/aios-install` |
| Wrapper | `/usr/local/bin/aios` |
| D-Bus | `/usr/bin/dbus-daemon` (`dbus.service`) |

## Referencia cruzada a la ISO

Para construir o personalizar la imagen live que contiene este agente, consulta `README-aios-lfs-v8.md`.

## Dependencias

- Python 3.11+
- `requests`, `pyyaml`
- llama.cpp compilado (`llama-server`)
- Modelo GGUF (Qwen3-8B)

## Historial de versiones

| Versión | Fecha | Cambios principales |
|---|---|---|
| v3.3 | 2026-07-27 | chat.py auto-arranque llama-server; ld.so.conf.d/llama.conf; aios-install grub.cfg fijo en modo texto; setup.py simplificado (solo Qwen3-8B, sin descarga); ISO build con `-iso-level 3` para modelos >4 GB |
| v3.2 | 2026-07-26 | setup.py: validación API key, bucle de reintento, fix backspace readline; aios-session: X primero, i3 con exec condicional; dbus.service; ldconfig.service masked; PATH+secure_path; aios-install sin `--force` (GRUB 0x9000) |
| v3.1 | 2026-07-24 | GRUB compilado desde LFS 13.0-systemd con fix de linker entry point 0x9000; ISO build con `grub-mkrescue` del host |
| v3.0 | 2026-07-21 | Wizard setup.py con opción INSTALL TO DISK; aios-install v1.0; chat.py wrapper EOF/errores |

## Licencia

MIT
