#!/usr/bin/env python3
"""Detecta la tarjeta de audio analógica y escribe asound.conf.

El asound.conf hardcodeado (plughw:1,0) solo sirve para UN hardware concreto
(A8-7410: HDMI=card0, analógica=card1). Aquí se elige la PRIMERA tarjeta que
NO sea HDMI/DisplayPort, para que el beep/audio funcione en cualquier equipo
(VBox, A8-7410, i5-1035G1...).
"""
import pathlib
import re


def detect_analog_card():
    try:
        text = pathlib.Path("/proc/asound/cards").read_text()
    except OSError:
        return 0
    cards = {}
    cur = None
    for line in text.splitlines():
        m = re.match(r"^\s*(\d+)\s*\[", line)
        if m:
            cur = int(m.group(1))
            cards[cur] = line
        elif cur is not None:
            cards[cur] += "\n" + line
    # primera tarjeta que NO sea HDMI/DisplayPort
    for c in sorted(cards):
        if not re.search(r"HDMI|DisplayPort|\bDP\b", cards[c], re.I):
            return c
    # fallback: la primera tarjeta, o 0
    return min(cards) if cards else 0


def _write(conf):
    # /etc/asound.conf (sistema); si no es escribible (squashfs ro sin overlay),
    # se cae a ~/.asoundrc (siempre escribible y tiene prioridad por usuario).
    for target in ("/etc/asound.conf", str(pathlib.Path.home() / ".asoundrc")):
        try:
            pathlib.Path(target).write_text(conf)
            return target
        except OSError:
            continue
    return None


def main():
    card = detect_analog_card()
    conf = (
        "pcm.!default {\n"
        "    type plug\n"
        f'    slave.pcm "plughw:{card},0"\n'
        "}\n"
        "ctl.!default {\n"
        "    type hw\n"
        f"    card {card}\n"
        "}\n"
    )
    where = _write(conf)
    if where:
        print(f"audio-detect: tarjeta analógica {card} -> {where}")
    else:
        print(f"audio-detect: no se pudo escribir asound.conf (tarjeta {card})")


if __name__ == "__main__":
    main()
