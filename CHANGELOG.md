# Changelog

## v3.7 - agosto 2026

### hito físico

- Se verificó el arranque completo de AIOS LFS en hardware real (portátil físico con SSD SATA) el 2 Ago 2026.
- La ISO arranca desde USB cuando se graba con Rufus en modo DD.
- El instalador copia el sistema al disco SSD y el equipo arranca desde disco con banner AIOS y login.
- Toda la cadena (live USB → instalación → arranque disco) funciona en hardware físico, no solo en VirtualBox.
- Se corrigió el init del initrd live para esperar la aparición del dispositivo de arranque durante 30 s, con loop de verificación `[ -b ]` y `break 2`.
- Se amplió la lista de dispositivos reconocidos en el init: `sdc`, `sdd`, `hd*`, `nvme*`, `mmcblk*`.
- Se reemplazó el kernel panic silencioso por el mensaje claro `AIOS: boot media not found` más shell de emergencia busybox.
- Se documentó que Rufus debe usarse en modo DD; el modo ISO crea FAT32 y el init busca iso9660, por lo que falla actualmente.

### próximos pasos

- Soportar Rufus modo ISO/FAT32 en el script init del initrd live.
- Compilar e integrar kernel #5 con soporte NVMe y UAS.

## v3.6 - agosto 2026

### aios-install v1.1.2

- **Fix: kernel panic al arrancar AIOS LFS desde disco duro.**
  El sistema instalado a disco mostraba el panic `'Attempted to kill init! exit code=0x7f00'` (127) justo tras el arranque.

#### Causas raíz

1. **Escape octal en el patrón `sed` de `build_disk_initrd`**: la cadena Python usaba un solo backslash en `'s/.*root=\([^ ]*\).*/\1/p'`. Python interpreta `\1` como el carácter de control SOH (`0x01`), que terminaba escrito en el `init` generado. Al ejecutarse, `sed` devolvía un dispositivo root fantasma y el posterior `mount -t ext4` fallaba.
2. **Fallback incorrecto en el initrd**: cuando `mount` fallaba, el script ejecutaba `exec /bin/sh`, pero en el initrd live transformado no existe `/bin/sh`; solo hay `init` y `bin/busybox`, sin symlinks de applets. El `exec` fallaba con código 127, matando el init y provocando el panic.
3. **Sin espera al dispositivo root**: el dispositivo de root podía no estar disponible en el instante en que el init lo consultaba, por lo que incluso con el dispositivo correcto el arranque era inestable.

#### Solución aplicada

- Se corrigió el patrón `sed`/`tail` usando doble backslash (`\\(` y `\\1`) para que el script `init` generado reciba literalmente `\(` y `\1`, y `sed` extraiga el dispositivo root correcto.
- Se añadió un bucle de espera activa de hasta 30 segundos hasta que el dispositivo root aparezca en `/dev`.
- Se reemplazó el fallback `exec /bin/sh` por `exec /bin/busybox sh`, que sí existe en el initrd.
- Se usa ahora `exec /bin/busybox switch_root /root /sbin/init` para continuar el arranque del sistema real.
- Se añadió `/bin/busybox` (estático, 2.1 MB, extraído del initrd) al squashfs del sistema live, ya que `build_disk_initrd` lo necesita y el sistema live no lo incluía.

#### Verificación

- Reinstalando AIOS LFS a disco, el arranque desde disco funciona correctamente: se muestra el logo AIOS y llega al login.
- Pendiente de pulir: GRUB sigue mostrando el mensaje `'Welcome to GRUB!'`. Futura mejora: `timeout_style=hidden` y `quiet_boot=1`.

## v3.4 - agosto 2026

### setup.py

- `validate_api_key` ejecuta la petición en un hilo daemon con `join(timeout=12)`; el timeout de `urlopen` no cubre resolución DNS y el menú cloud se colgaba sin límite.
- Al final de `__main__` se usa `os._exit(0)` para forzar la salida sin esperar a hilos residuales.
- La API key se guarda correctamente en `~/.aios/.env` (corregido el bug `if not key:` → `if key:`).
- Menú LOCAL actualizado con el modelo `Qwen3-8B-Instruct` y el texto `"1) LOCAL (no internet) / Simple tasks"`.
- `print_box` se centra en pantalla usando `os.get_terminal_size`, con padding horizontal y vertical.
- Mensaje final del setup: `"Setup complete. Starting the AIOS agent..."`, reflejando el paso automático de setup a aios.

## v3.5 - agosto 2026

### aios-install

- **v1.1.0**: permitir cambiar las contraseñas `root` y `aios` durante la instalación. Se usa `getpass`, longitud mínima de 8 caracteres y `chpasswd` vía chroot por stdin. El resumen final omite `"Login: aios/aios"` si se cambiaron las credenciales.
- **v1.1.1**: silent boot en disco. El `grub.cfg` generado usa `timeout=0`, `quiet`, `systemd.show_status=false`, `initrd /boot/initrd.img` y `root=` real. `build_disk_initrd` transforma el initrd live conservando el banner y reemplazando el bucle ISO por `mount root` + `switch_root /sbin/init`.
- Se elimina `nokaslr` del `grub.cfg` generado.
- `print_box` centrado en pantalla.

## v2.7.1 — Fix del bootloader GRUB en instalaciones a disco (VirtualBox)

- `scripts/aios-install`: se reemplaza la generación dinámica del menú GRUB (`grub-mkconfig`) por un `grub.cfg` fijo en modo texto.
- Motivación: `grub-mkconfig` generaba un menú gráfico (`load_video`, `insmod all_video`, `gfxpayload=keep`, `terminal_output gfxterm`, `menuentry "Arch GNU/Linux"`) que colgaba en VirtualBox mostrando `Cargando Linux 6.18.10-lfs ...`.
- Nuevo `grub.cfg` generado por `install_grub()`:
  - `set default=0`
  - `set timeout=5`
  - `menuentry "AIOS LFS" { linux /boot/vmlinuz-6.18.10-lfs root=/dev/sda2 rw nokaslr console=tty0 loglevel=6 }`
- Se mantiene `grub-install` para escribir el bootloader en el disco destino.
- Se eliminan UUID y referencias a "Arch Linux" del menú de arranque.
- README.md actualizado con sección "Fix v7: GRUB gráfico cuelga en VirtualBox tras instalación a disco".

## v2.1 — SRE Agent con function calling nativo sobre Qwen2.5-7B-Instruct

- Modelo definitivo fijado en Qwen2.5-7B-Instruct; descartados Qwen2.5-Coder-3B y otros modelos <7B por function calling poco fiable.
- 13 tools: `run_command`, `read_file`, `write_file`, `web_search`, `git_operation`, `mcp_call`, `run_playbook`, `process_start`, `process_send`, `process_close`, `process_list`, `cloud_reasoning`, `get_context_usage`.
- Memoria procedural Skill-Pro, compresión de contexto con conteo real de tokens vía `/v1/tokenize`, sesión persistente y recuperación de errores apt.
- Historial readline, navegación con cursores y Ctrl+C que interrumpe el turno actual sin salir del chat.
- Setup wizard (`setup.py`) con modos local/cloud/híbrido y 7 proveedores (DeepSeek V4 Flash/Pro, OpenAI, Anthropic, Google, Kimi, Ollama Cloud, OpenRouter); sesiones y memoria separadas por modo; `context_limit` por proveedor en `data/config.yaml`.
- Detección automática de RAM desde `/proc/meminfo` y escalado automático del contexto local: ≤8 GB → 8K, 12–16 GB → 32K, >16 GB → 64K.
- Asignación automática de threads CPU al 87.5% de los cores (p. ej. 14/16); el menú muestra `N/16 cores` en lugar de porcentaje.
- `cloud_reasoning` delega razonamiento complejo al cloud con el contexto local completo; `get_context_usage` muestra tokens usados vs. máximo.
- Compresión por modo: 95% del contexto local (32K por defecto) para local/híbrido, 50% del `context_limit` para cloud.
- Anti-bucle: si la misma tool + argumentos se repite ≥3 veces, se pregunta al usuario si abortar con timeout de 10 s.
- Correcciones: Docker `--format` ya no se marca como destructivo; endpoint local/híbrido corregido a `/v1/chat/completions`; API key oculta con `getpass`; se muestra N/16 cores; DeepSeek actualizado a V4 Flash y V4 Pro; añadido Ollama Cloud como proveedor; `.gitignore` actualizado con `gcc*`; disclaimer de responsabilidad en README; RAM mínima local subida de 8 GB a 12 GB.
- README.md y PDF ejecutivo actualizados.

## v2.0 — Agente SRE con function calling nativo sobre Qwen3-8B

- Reescritura completa del repositorio.
- Agente ligero de SRE con function calling nativo vía llama.cpp server.
- Nuevas herramientas:
  - `run_command`: ejecuta comandos shell en Linux.
  - `read_file`: lee archivos de configuración y logs.
  - `write_file`: escribe archivos, bloqueando rutas de sistema críticas.
- Soporte conversacional en español con hasta 5 turnos de razonamiento.
- Seguridad básica: advertencia antes de comandos destructivos y bloqueo de `/etc`, `/boot`, `/sys`, `/proc`, `/dev`.
- CLI interactivo en `chat.py`.
- README.md y PDF ejecutivo en `docs/ejecutivo.pdf`.
