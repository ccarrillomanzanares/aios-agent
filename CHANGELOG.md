# Changelog

## v3.15 - agosto 2026

### fixes del arranque del LLM y del pantallazo (regresión de la barra de progreso)

- **Carga del LLM clavada al 85%**: `_start_local_model` usaba `select` sobre el fd crudo + `readline` con buffer de Python. Cuando llama-server escribía `model loaded` y `listening` casi a la vez, `readline` leía las dos líneas al buffer pero devolvía solo la primera; `listening` quedaba atascada en el buffer (select mira el fd, no el buffer) y la barra se quedaba en 85% para siempre **aunque el servidor ya escuchara** (por eso 0% CPU y "no termina"). Fix: **hilo lector + cola** (sin select) que drena el stdout y detecta `listening` de verdad; timeout de 15 min y volcado de las últimas líneas si no arranca.
- **Printscreen (`Print`)**: el `scrot` inline en i3 con `%` (strftime) + `&&` + comillas anidadas rompía el parser de i3 (`Could not translate string to key symbol`). Fix: script `scripts/screenshot.sh` dedicado, y binding a `/usr/local/bin/aios-agent/scripts/screenshot.sh`.

## v3.14 - agosto 2026

### agente: ejecuta tools de verdad (feedback Carlos)

- **`import sys` en `agent.py`**: `_out()` y `_cbreak_on()` usaban `sys` sin importarlo → `NameError` que el `except` del stream se tragaba en silencio (el agente parecía "mudo"; al `shutdown` saltaba el error). Fix raíz.
- **Tool visible antes de ejecutar**: el `⚙ tool(...)` se muestra ANTES de `execute_tool` — un comando largo ya no parece que "no hace nada".
- **`run_command` con stdin correcto**: `/dev/null` por defecto (un prompt interactivo ya no bloquea en silencio) y auto-`y` para `sven install/upgrade/update` (el `:: Proceed? [Y/n]` ya no cuelga).
- **Tool `list_desktop_apps`**: parsea `/usr/share/applications/*.desktop` — el agente responde "qué apps hay" buscando de verdad (p. ej. Firefox), no de memoria.
- **Grounding**: "sven siempre con sudo" + "nunca termines el turno con voy-a-hacerlo; emite el tool_call en el mismo turno" + "usa list_desktop_apps".

### carga del LLM local

- **Barra de progreso real** en `chat.py` `_start_local_model`: fases reales del log de llama-server (`loading model` → `init` → `model loaded` → `listening`) con porcentaje y tiempo, en vez de 30s fijos. Si no arranca, vuelca el log capturado.

### pantallazos y diagnóstico

- **Printscreen (`Print`)**: `scrot` a `~/screenshots/shot-<timestamp>.png`; documentado en `shortcuts.txt` junto a los comandos de chat `/think /health /reset /stats`.
- **`aios-diag`**: recopila diagnóstico (sistema + errores + logs AIOS + pantallazos desde la última recolección), redacta claves de `config.yaml`, comprime `tar.zst` con timestamp y sube por rsync a una cuenta `diag` de SOLO escritura (rrsync, sin shell/sudo). La clave no va en la ISO (`--local` = solo local).

## v3.13 - agosto 2026

### fixes de estabilidad (feedback Arnold / portátiles físicos)

- **Bucle live→menú**: `_live_flow` devuelve `True` al completar y `main()` hace `break` — antes "Setup complete" no terminaba y volvía al menú en bucle.
- **Internet con reintento**: `_wait_internet()` espera al DHCP tras asociar el WiFi antes de declarar "no internet" (antes falso negativo inmediato).
- **Delete/flechas en `_read_line`**: manejo de secuencias de escape (`\x1b`, Delete xterm/rxvt) en los inputs del formulario.
- **sven timeout 600s**: `run_command` da timeout generoso a `sven install/upgrade/sync` (antes daba timeout a los minutos).
- **Chat sin efecto escalera**: `_out()` escribe CRLF explícito en la salida del LLM (streaming, tools y salto final). Antes escribía salto de línea simple confiando en ONLCR del tty y el cursor no volvía a col 0 → cada prompt se desplazaba a la derecha.

## v3.12 - agosto 2026

### soporte ollama-hardened (Moonlight) como proveedor

- **X-API-Key**: `auth_type` en config (bearer/x-api-key); `CLOUD_HEADERS` usa `X-API-Key` para hardened. `verify=False` solo x-api-key (cert self-signed).
- **Proveedor "Ollama Hardened"**: `https://webuillama.ccmai.org:8443/v1/chat/completions`, Moonlight-16B-A3B Q3_K_M. Key en `~/.aios/.env` (privada, no en ISO).
- **Fix lectura de key** del proveedor custom (`provider_env`).
- **Caddyfile hardened** (repo ollama-hardened): rutas API → 401 sin key válida.

## v3.11 - agosto 2026

### mejoras al LLM local (precisión / anti-alucinación)

- **Grounding AIOS**: `_AIOS_GROUNDING` inyecta los invariantes de AIOS en el system prompt (LFS, `sven` como único gestor — nunca apt/dnf/pacman, systemd, i3, red con systemd-networkd + wpa_supplicant sin ctrl_interface, usrmerge, `aios-update`/`aios-install`, grabación `$mod+Print`). Evita que el modelo invente comandos de otras distros.
- **Disciplina de verificación**: regla en el prompt — para preguntas sobre el estado ACTUAL del sistema (RAM/disco/procesos/servicios), comprobar con tool primero, nunca responder de memoria.
- **Sampling según doc oficial de Qwen3**: `_sampling_params()` — thinking `temp 0.6/top_p 0.95/top_k 20/min_p 0`, no-thinking `0.7/0.8/20/0`; cloud mantiene temperatura conservadora. Verificado A/B en VPS (b10655): misma respuesta correcta, sin repeticiones.
- **Eco del reasoning_content**: el agente captura y devuelve `reasoning_content` en el historial multi-turno (thinking limpio en conversaciones largas).

## v3.10 - agosto 2026

### switch thinking local (ON/OFF) + context/threads relativos en instalación a disco

- **Thinking mode local (Qwen3-8B)**: switch binario ON/OFF vía clave `local.think` en `config.yaml` (default OFF).
  - `agent.py`: `THINK_LOCAL` (env `AIOS_LOCAL_THINK`) controla el token `/no_think` de la consulta, la regla "Do not use <think> tags" del system prompt y el `max_tokens` (mín. 2048 al pensar, porque el razonamiento consume tokens antes de la respuesta). `_quick_llm` sigue siempre con `/no_think`.
  - `chat.py`: pasa `AIOS_LOCAL_THINK` al entorno antes de importar `agent`.
  - `setup.py`: pregunta "Enable thinking mode? [y/N]" en live e install.
  - `aios-install`: nuevo flag `--think 0|1`.
- **Verificado empíricamente (VPS, llama.cpp b10655)**: con `/think`, el razonamiento de Qwen3 va en `delta.reasoning_content` (campo SEPARADO), NO inline en `delta.content`. El agente solo lee `content`/`tool_calls`, así que el razonamiento no se imprime ni contamina la respuesta; `_clean` queda como safety net.
- **Fix context/threads en instalación a disco**: `aios-install` escribía `threads: 14` y `context: 32768` hardcodeados; ahora usa `_detect_cpu()` y `_auto_context(_detect_ram_gb())` (espejo de `setup.py`), coherente con el live y sin lanzar llama-server con `-c 32768` en máquinas ≤8 GB.
- **Comando `/think` en caliente**: toggle del thinking sin salir del agente (como `/sound`); persiste en `config.yaml` y `agent.set_think()` regenera token + `max_tokens` + system prompt en runtime. Documentado en `shortcuts.txt` (aios-lfs).

## v3.9 - agosto 2026

### fix: agente mudo (respuesta en blanco + prompt >)

- **Sintoma**: el agente dejaba de responder (respuesta en blanco, prompt ">", sin ejecucion de tools) cuando el modelo devolvia tool calls largas con coordenadas de vision (p.ej. OCR TSV "805,316,5x3") y ocasionalmente sin ellas.
- **Causa raiz**: chat.py tragaba en silencio el retorno de agent.run() (solo print() de salto de linea) -> cualquier error o "(respuesta vacia del modelo)" quedaba invisible. Ademas, si el stream del LLM se cortaba sin finish_reason (servidor cerraba a mitad de tool call), content quedaba vacio y el agente se rendia sin reintentar.
- **Fixes**:
  1. chat.py: el retorno de agent.run() se muestra si no vino por el stream (errores y respuesta vacia ya no son mudos).
  2. agent.py: log crudo del stream SSE en /tmp/aios-stream.log (lineas data: + marcador END con finish_reason/chunks/tools + excepciones) para diagnostico.
  3. agent.py: reintento unico si el stream termina sin finish_reason y sin contenido ("⚠️ Stream vacio (posible corte). Reintentando...").
- Verificado en portatil fisico (4 Ago 2026): tras reiniciar el agente, responde con normalidad. Pendiente confirmacion a largo plazo del caso de coordenadas.

# Changelog

## v3.8 - agosto 2026

### kernel de distro (#5) - hardware generico

- Config del kernel 6.18.10 ampliada: wifi (iwlwifi, ath9k/10k/11k, rtw88/89, rtl8xxxu, brcmfmac, rtlwifi/rtl8723be/rtl8821ae), DRM (i915/amdgpu/nouveau), NVMe, UAS, I2C_HID_ACPI, ethernet (r8169/e1000e/igb), ALSA HDA + USB audio (=m via udev; criticos =y).
- Firmware linux-firmware en /lib/firmware (~534MB) + symlinks iwlwifi (intel/iwlwifi -> raiz) + regulatory.db + rtl_nic.
- Verificado en HP Notebook (AMD APU + Realtek RTL8723BE + RTL8106E): wifi, ethernet, audio (alc269 + HDMI), touchpad Synaptics.

### setup.py - opcion 5 WIFI SETUP

- Nueva opcion de menu: detecta interfaz wifi, escanea SSIDs, genera /etc/wpa_supplicant/wpa_supplicant-<iface>.conf (wpa_passphrase), conecta con wpa_supplicant y verifica conectividad.
- Verificacion de internet con urllib contra example.com/archlinux.org: en el sistema no existen curl/ping y 1.1.1.1 devuelve 403 a urllib.
- Persistencia en sistema instalado: habilita wpa_supplicant@<iface> y crea /etc/systemd/network/20-wifi-dhcp.network (systemd-networkd DHCP en wl*, mismo mecanismo que el ethernet en*).
- Fix de bug: el unit aios-wifi.service usaba /usr/sbin/wpa_supplicant (ruta inexistente; Arch lo instala en /usr/bin) -> 203/EXEC -> wifi asociada sin IP al arranque. Sustituido por networkd.

### infraestructura y dependencias

- sven: sincronizacion de bases (sven sync) + registro manual JSON en /var/lib/sven/installed/ para paquetes con estado fantasma (pcsclite, libinput, libgudev) - paquetes marcados instalados sin archivos.
- libinput.so.10 + libgudev-1.0.so.0 + libwacom + liblua instalados (cadena de dependencias del driver libinput del Xorg) -> touchpad Synaptics funcional en hardware real.
- busybox: symlinks de applets (/bin/udhcpc, /sbin/udhcpc) + default.script en /usr/share/udhcpc y /etc/udhcpc (el busybox de Ubuntu busca la ruta compilada /etc/udhcpc/).
- HITO: AIOS completo en hardware real - wifi al arranque sin cable, agente cloud funcional (4 Ago 2026).

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

- `aios-install`: se reemplaza la generación dinámica del menú GRUB (`grub-mkconfig`) por un `grub.cfg` fijo en modo texto.
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
