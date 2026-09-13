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

# Pick the ANALOG card, not the first one. `awk '{print $1; exit}'` always
# returned card 0, which on machines with an HDMI output is the HDMI card: no
# speaker, so no sound, and the volume keys moved a mixer that does not exist.
# Same rule as scripts/audio-detect.py: prefer a card that is not HDMI/DP.
CARD=""
while read -r _id _name _rest; do
    case "$_name" in
        *HDMI*|*"DisplayPort"*) continue ;;
    esac
    CARD="$_id"
    break
done <<< "$(sed -n 's/^ *\([0-9]\+\) *\[ *\([^]]*\)\].*/\1 \2/p' /proc/asound/cards)"
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

echo "== [2/5] Mixer (by control NAME, not numid) =="
# numid=3/4 were copied from AC'97 hardware, where they are "Master Mono". On
# the ALC3227 they are 'Speaker Playback Volume' and 'Speaker Playback Switch',
# so `cset numid=4 60,60` (a 60,60 on a BOOLEAN) failed silently -- hence the
# `|| true` that hid it. Use names, and only ones that exist.
amixer -c "$CARD" sset 'Master' 100% unmute >/dev/null 2>&1 || true
amixer -c "$CARD" sset 'Speaker' 100% unmute >/dev/null 2>&1 || true
amixer -c "$CARD" sset 'PCM' 100% unmute >/dev/null 2>&1 || true
# Auto-Mute mutes the speaker when headphones are plugged in; disable it so a
# plugged jack cannot silence the laptop speaker.
amixer -c "$CARD" sset 'Auto-Mute Mode' Disabled >/dev/null 2>&1 || true
amixer -c "$CARD" sget 'Master' 2>/dev/null | grep -E 'Mono:|Front Left:' | sed 's/^/  /' || true
alsactl store 2>/dev/null && echo "  alsactl store OK" || echo "  (alsactl store not available)"

echo "== [3/5] STT vosk =="
# vosk SHIPS with AIOS: only check it. Do NOT pip-install it -- that is exactly
# the blind "install vosk" the agent tried on its own, believing it was missing.
if python3 -c "import vosk" 2>/dev/null; then
    echo "  vosk already installed ($(python3 -c 'import vosk; print(vosk.__version__)' 2>/dev/null))"
else
    echo "  !! vosk NOT importable -- reinstall with: sven install vosk  (do NOT pip install)"
fi
# The monolingual models ship INSIDE the ISO (7 languages, as aios-largo):
# never download them at runtime.
MODEL=/usr/local/share/aios/vosk-model-es
if [ -d "$MODEL" ]; then
    echo "  model already present ($MODEL)"
else
    echo "  !! model missing: $MODEL"
    echo "     It is part of the ISO; reinstall or copy it. Do not wget it."
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
