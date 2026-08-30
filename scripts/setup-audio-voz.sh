#!/usr/bin/env bash
# setup-audio-voz.sh — aplica los arreglos de audio / voz / STT de AIOS.
#
# Origen: sesión de diagnóstico (audio mudo, tic del typewriter, /voice sin
# parar, /mic sin oír). Reproduce en cualquier AIOS:
#   1) /etc/asound.conf apuntando a la tarjeta de sonido real
#      (síntoma: aplay -> "Cannot get card index for 1", sin tic ni voz)
#   2) Mezclador: activa "Master Mono Playback" (altavoz AC'97) y guarda estado
#      (síntoma: tarjeta OK pero silencio total)
#   3) STT vosk: paquete sven + bindings Python + modelo español
#      (síntoma: /mic responde "(No speech detected)")
#   4) Verificaciones finales (aplay, vosk, espeak-ng)
#
# Uso:  sudo ./setup-audio-voz.sh        (idempotente, re-ejecutable)
set -u

[ "$(id -u)" = 0 ] || { echo "  Ejecuta como root: sudo $0"; exit 1; }

CARD=$(awk '{print $1; exit}' /proc/asound/cards 2>/dev/null)
CARD=${CARD:-0}
echo "== [1/5] /etc/asound.conf (tarjeta $CARD) =="
cat > /etc/asound.conf <<EOF
pcm.!default {
    type plug
    slave.pcm "plughw:${CARD},0"
}
ctl.!default {
    type hw
    card ${CARD}
}
EOF
echo "  escrito: plughw:${CARD},0"

echo "== [2/5] Mezclador (Master Mono + estado) =="
amixer -c "$CARD" cset numid=3 1,1 >/dev/null 2>&1 || true   # Master Mono Playback Switch: on
amixer -c "$CARD" cset numid=4 60,60 >/dev/null 2>&1 || true # Master Mono Playback Volume: 60/63
alsactl store 2>/dev/null && echo "  alsactl store OK" || echo "  (alsactl store no disponible)"

echo "== [3/5] STT vosk =="
if ! python3 -c "import vosk" 2>/dev/null; then
    echo "  instalando vosk-api (librería C)..."
    echo y | python3 /usr/lib/sven/run_sven.py install vosk-api 2>&1 | tail -1
    echo "  instalando bindings Python..."
    pip3 install --break-system-packages vosk 2>&1 | tail -1
else
    echo "  vosk ya instalado"
fi
MODEL=/usr/local/share/aios/vosk-model-es
if [ ! -d "$MODEL" ]; then
    echo "  descargando modelo español (~40 MB)..."
    mkdir -p /usr/local/share/aios
    cd /tmp || exit 1
    wget -q https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip -O vosk-model-small-es.zip
    python3 -c "
import zipfile, shutil, os
z = zipfile.ZipFile('/tmp/vosk-model-small-es.zip')
z.extractall('/usr/local/share/aios/')
z.close()
shutil.move('/usr/local/share/aios/vosk-model-small-es-0.42', '$MODEL')"
    chown -R aios:wheel "$MODEL" 2>/dev/null || true
else
    echo "  modelo ya presente ($MODEL)"
fi

echo "== [4/5] Verificaciones =="
python3 - <<'PY'
import subprocess, math, struct
pcm = b"".join(struct.pack("<h", int(8000*math.sin(2*math.pi*880*i/44100))) for i in range(4410))
try:
    r = subprocess.run(["aplay","-q","-f","S16_LE","-r","44100","-c","1"], input=pcm, timeout=10)
    print("  aplay :", "OK" if r.returncode == 0 else "FAIL")
except Exception as e:
    print("  aplay : FAIL -", e)
PY
python3 -c "import vosk; print('  vosk  : OK')" 2>&1 | tail -1
if command -v espeak-ng >/dev/null 2>&1; then
    echo "  espeak: OK ($(espeak-ng --version 2>&1 | head -1))"
else
    echo "  espeak: FALTA — instala con: sven install espeak-ng"
fi

echo "== [5/5] Listo. Reinicia el chat para cargar los parches (voice.stop, errores visibles). =="
