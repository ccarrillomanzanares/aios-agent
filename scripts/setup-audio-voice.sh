#!/usr/bin/env bash
# setup-audio-voice.sh — applies AIOS audio / voice / STT fixes.
#
# Origin: diagnostic session (muted audio, typewriter tick, /voice not
# stopping, /mic not hearing). Reproduces on any AIOS:
#   1) /etc/asound.conf pointing to the real sound card
#      (symptom: aplay -> "Cannot get card index for 1", no tick or voice)
#   2) Mixer: enables "Master Mono Playback" (AC'97 speaker) and saves state
#      (symptom: card OK but total silence)
#   3) STT vosk: sven package + Python bindings + Spanish model
#      (symptom: /mic replies "(No speech detected)")
#   4) Final checks (aplay, vosk, espeak-ng)
#
# Usage:  sudo ./setup-audio-voice.sh        (idempotent, re-runnable)
set -u

[ "$(id -u)" = 0 ] || { echo "  Run as root: sudo $0"; exit 1; }

CARD=$(awk '{print $1; exit}' /proc/asound/cards 2>/dev/null)
CARD=${CARD:-0}
echo "== [1/5] /etc/asound.conf (card $CARD) =="
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
echo "  written: plughw:${CARD},0"

echo "== [2/5] Mixer (Master Mono + state) =="
amixer -c "$CARD" cset numid=3 1,1 >/dev/null 2>&1 || true   # Master Mono Playback Switch: on
amixer -c "$CARD" cset numid=4 60,60 >/dev/null 2>&1 || true # Master Mono Playback Volume: 60/63
alsactl store 2>/dev/null && echo "  alsactl store OK" || echo "  (alsactl store not available)"

echo "== [3/5] STT vosk =="
if ! python3 -c "import vosk" 2>/dev/null; then
    echo "  installing vosk-api (C library)..."
    echo y | python3 /usr/lib/sven/run_sven.py install vosk-api 2>&1 | tail -1
    echo "  installing Python bindings..."
    pip3 install --break-system-packages vosk 2>&1 | tail -1
else
    echo "  vosk already installed"
fi
MODEL=/usr/local/share/aios/vosk-model-es
if [ ! -d "$MODEL" ]; then
    echo "  downloading Spanish model (~40 MB)..."
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
    echo "  model already present ($MODEL)"
fi

echo "== [4/5] Checks =="
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
    echo "  espeak: MISSING — install with: sven install espeak-ng"
fi

echo "== [5/5] Done. Restart the chat to load the patches (voice.stop, visible errors). =="
